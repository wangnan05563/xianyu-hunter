"""对 bge-small-zh-v1.5 的 fp32 ONNX 做 int8 动态量化（构建期一次性运行，仅需 onnxruntime + onnx）

用途：在 scripts/export_embedding_onnx.py 生成 fp32 工件（bge_small_zh.onnx）之后，
进一步把权重量化成 int8（QInt8），使运行期加载体积与内存占用再降约 40–50MB
（90.5MB → ~45MB），最终分发包瘦身二次收益。

量化方式：dynamic quantization（仅量化权重 MatMul / Gemm 的 initializer 为 int8，
激活保持 fp32）。对 embedding 这类"同分布、只做最近邻检索"的任务，余弦相似度
与 fp32 几乎无差异（实测 > 0.99）。图内 CLS pooling + L2 归一化（Div/ReduceL2/Sqrt）
不参与量化，输出语义不变。

运行期（onnx_embedding.py）会优先加载 bge_small_zh.int8.onnx（若存在），缺失则回退 fp32。
本脚本幂等：目标已存在则跳过（除非 --force）。

运行：
  python scripts/quantize_embedding_onnx.py
  python scripts/quantize_embedding_onnx.py --in-dir path --out-dir path
  python scripts/quantize_embedding_onnx.py --verify      # 量化后自检余弦
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from onnxruntime.quantization import QuantType, quantize_dynamic

# 仅量化权重矩阵（transformer 的主体）。Gather（embedding 查表）体量小、量化易掉点，不动。
# Conv 在 bge 中不存在，列出来无害（quantize_dynamic 只处理图中实际出现的 op）。
_OP_TYPES_TO_QUANTIZE = ["MatMul", "Gemm", "Conv"]

_FP32_NAME = "bge_small_zh.onnx"
_INT8_NAME = "bge_small_zh.int8.onnx"


def _default_embedding_dir() -> str:
    return os.path.abspath(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "src", "xianyu_hunter", "resources", "embedding",
        )
    )


def quantize(
    in_path: str,
    out_path: str,
    per_channel: bool = True,
    force: bool = False,
) -> str:
    """对 fp32 ONNX 做 int8 动态量化，返回输出路径。

    per_channel=True：权重按输出通道分别定标，比 per-tensor 精度更好（推荐）。
    """
    if os.path.isfile(out_path) and not force:
        print(f"[quantize] 已存在，跳过：{out_path}（用 --force 覆盖）")
        return out_path

    if not os.path.isfile(in_path):
        raise FileNotFoundError(f"fp32 ONNX 不存在：{in_path}，请先运行 export_embedding_onnx.py")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    quantize_dynamic(
        model_input=in_path,
        model_output=out_path,
        op_types_to_quantize=_OP_TYPES_TO_QUANTIZE,
        per_channel=per_channel,
        reduce_range=False,  # x86/ARM CPU 用全范围 int8（[-127,127]），精度更优
        weight_type=QuantType.QInt8,
    )

    in_sz = os.path.getsize(in_path) / 1024 / 1024
    out_sz = os.path.getsize(out_path) / 1024 / 1024
    print(
        f"[quantize] {os.path.basename(in_path)} ({in_sz:.1f} MB) -> "
        f"{os.path.basename(out_path)} ({out_sz:.1f} MB) "
        f"节省 {in_sz - out_sz:.1f} MB ({(1 - out_sz / in_sz) * 100:.1f}%)"
    )
    return out_path


def _verify(in_path: str, out_path: str) -> float:
    """加载 fp32 与 int8 两个 ONNX，对若干样本比对余弦相似度最小值。"""
    import onnxruntime as ort

    texts = [
        "iPhone 15 的电池续航怎么样",
        "二手闲置交易平台的担保交易流程",
        "Python 装饰器的高级用法",
        "如何快速卖出闲置的相机镜头",
        "机器学习中的向量检索原理",
    ]
    ids = _ONNX_INPUT_IDS
    mask = _ONNX_INPUT_MASK
    out = _ONNX_OUTPUT

    sess_fp = ort.InferenceSession(in_path, providers=["CPUExecutionProvider"])
    sess_i8 = ort.InferenceSession(out_path, providers=["CPUExecutionProvider"])
    tok_path = os.path.join(os.path.dirname(out_path), "tokenizer.json")
    from tokenizers import Tokenizer

    tok = Tokenizer.from_file(tok_path)

    def _vecs(sess):
        encs = tok.encode_batch(texts)
        max_len = min(512, max(len(e.ids) for e in encs))
        id_arr = np.array([e.ids[:max_len] + [0] * (max_len - len(e.ids[:max_len])) for e in encs], dtype=np.int64)
        m_arr = np.array([[1] * len(e.ids[:max_len]) + [0] * (max_len - len(e.ids[:max_len])) for e in encs], dtype=np.int64)
        res = sess.run(None, {ids: id_arr, mask: m_arr})[0]
        return res / (np.linalg.norm(res, axis=1, keepdims=True) + 1e-12)

    v_fp = _vecs(sess_fp)
    v_i8 = _vecs(sess_i8)
    cos = (v_fp * v_i8).sum(axis=1)
    print(f"[verify] int8 vs fp32 余弦：min={cos.min():.5f} mean={cos.mean():.5f}")
    return float(cos.min())


# ONNX 图 I/O 名（须与 onnx_embedding.py / export 脚本一致）
_ONNX_INPUT_IDS = "input_ids"
_ONNX_INPUT_MASK = "attention_mask"
_ONNX_OUTPUT = "embedding"


def main() -> int:
    parser = argparse.ArgumentParser(description="bge ONNX int8 动态量化")
    parser.add_argument(
        "--in-dir",
        default=_default_embedding_dir(),
        help="含 fp32 bge_small_zh.onnx 的目录（默认 resources/embedding）",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="int8 输出目录（默认与 --in-dir 相同）",
    )
    parser.add_argument("--force", action="store_true", help="覆盖已存在的 int8 文件")
    parser.add_argument("--verify", action="store_true", help="量化后自检余弦相似度")
    parser.add_argument("--per-tensor", action="store_true",
                        help="用 per-tensor 量化（默认 per-channel，精度更好）")
    args = parser.parse_args()

    in_dir = os.path.abspath(args.in_dir)
    out_dir = os.path.abspath(args.out_dir) if args.out_dir else in_dir
    in_path = os.path.join(in_dir, _FP32_NAME)
    out_path = os.path.join(out_dir, _INT8_NAME)

    quantize(in_path, out_path, per_channel=not args.per_tensor, force=args.force)

    if args.verify:
        _verify(in_path, out_path)

    print(f"[quantize] 完成。运行期 OnnxEmbeddingBackend 会优先加载 {_INT8_NAME}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
