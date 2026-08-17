"""导出 bge-small-zh-v1.5 为 ONNX + tokenizer 工件（构建期一次性运行，需 torch）

用途：生成 OnnxEmbeddingBackend 运行期需要的产物，使最终分发包可移除 torch /
sentence-transformers / transformers（约 -320MB）。

输出目录（默认）：backend/xianyu_hunter/resources/embedding/
  - bge_small_zh.onnx   单一图：transformer + CLS pooling + L2 归一化（输出已归一化）
  - tokenizer.json      由完整 vocab 构建的 tokenizers.WordPiece（含 "iphone" 等 Latin token）
  - meta.json           记录源模型名与维度，便于排查

关键坑（已在可行性验证中定位并修复）：
1. 池化方式：bge 的 ST 流水线是 CLS-token pooling + L2 归一化（不是 mean pooling）。
   错误用 mean 会导致与 sentence-transformers 余弦仅 0.86；用 CLS + F.normalize(p=2) 后为 1.0。
2. 分词器词表：裸 tokenizers.Tokenizer.from_file(tokenizer.json) 的 WordPiece 词表不完整，
   "iPhone" 等 Latin token 会变 [UNK](id 100)，混合文本余弦掉到 0.92。
   修复＝用参考分词器的 get_vocab()（完整 21128 词）重建 WordPiece。

参考模型来源（二选一，自动回退）：
- 优先 sentence_transformers（与运行期 LocalEmbeddingBackend 完全一致）
- 缺失时（如瘦身后环境）回退 transformers.AutoModel + AutoTokenizer
  （bge-small-zh-v1.5 本质是 BERT，ST 只是其薄封装，两者 CLS+L2 输出一致）

运行：
  python scripts/export_embedding_onnx.py
  python scripts/export_embedding_onnx.py --model BAAI/bge-small-zh-v1.5 --out-dir path/to/dir
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import torch
import torch.nn as nn

# 离线优先：模型已缓存在 ~/.cache/huggingface/hub
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
# 若希望强制离线（避免任何网络试探），可设 HF_HUB_OFFLINE=1


class _BgeOnnxWrapper(nn.Module):
    """transformer + CLS pooling + L2 归一化（与 sentence-transformers 流水线一致）"""

    def __init__(self, base: nn.Module) -> None:
        super().__init__()
        self.base = base

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        out = self.base(input_ids=input_ids, attention_mask=attention_mask)
        cls = out.last_hidden_state[:, 0, :]  # CLS token
        return torch.nn.functional.normalize(cls, p=2, dim=1)


def _load_reference(model_name: str):
    """加载参考模型，返回 (base_model, tokenizer, dim, source)

    source = "sentence_transformers" 或 "transformers"。
    优先 sentence_transformers（与运行期 LocalEmbeddingBackend 一致），
    缺失则回退 transformers（bge 是 BERT 薄封装，CLS+L2 输出等价）。
    """
    try:
        from sentence_transformers import SentenceTransformer
        st = SentenceTransformer(model_name, device="cpu")
        base = st[0].auto_model
        tok = st.tokenizer
        dim = st.get_embedding_dimension()
        return base, tok, dim, "sentence_transformers"
    except Exception as e:
        print(f"[export] sentence_transformers 不可用（{type(e).__name__}: {e}），回退 transformers")
        from transformers import AutoModel, AutoTokenizer
        base = AutoModel.from_pretrained(model_name)
        tok = AutoTokenizer.from_pretrained(model_name)
        dim = base.config.hidden_size
        return base, tok, dim, "transformers"


def export(model_name: str, out_dir: str) -> dict:
    from tokenizers import Tokenizer, models, pre_tokenizers, normalizers, processors

    os.makedirs(out_dir, exist_ok=True)
    onnx_path = os.path.join(out_dir, "bge_small_zh.onnx")
    tok_path = os.path.join(out_dir, "tokenizer.json")
    meta_path = os.path.join(out_dir, "meta.json")

    # 1) 加载参考模型（离线缓存）
    base, tok, dim, source = _load_reference(model_name)
    base.eval()

    # 2) 导出 ONNX（legacy 导出器，避免拉 onnxscript）
    wrapper = _BgeOnnxWrapper(base)
    dummy_ids = torch.ones(2, 32, dtype=torch.long)
    dummy_mask = torch.ones(2, 32, dtype=torch.long)
    torch.onnx.export(
        wrapper,
        (dummy_ids, dummy_mask),
        onnx_path,
        input_names=["input_ids", "attention_mask"],
        output_names=["embedding"],
        dynamic_axes={
            "input_ids": [0, 1],
            "attention_mask": [0, 1],
            "embedding": [0],
        },
        opset_version=14,
        do_constant_folding=True,
        dynamo=False,
    )

    # 3) 用完整 vocab 重建 tokenizers.WordPiece（规避 tokenizer.json 词表不全坑）
    #    get_vocab() 返回完整 词->id 映射（含 "iphone"=8210），可靠。
    vocab = tok.get_vocab()
    wordpiece = Tokenizer(models.WordPiece(vocab, unk_token="[UNK]"))
    wordpiece.normalizer = normalizers.BertNormalizer(lowercase=True, strip_accents=True)
    wordpiece.pre_tokenizer = pre_tokenizers.BertPreTokenizer()
    wordpiece.post_processor = processors.TemplateProcessing(
        single="[CLS] $A [SEP]",
        special_tokens=[("[CLS]", 101), ("[SEP]", 102)],
    )
    wordpiece.save(tok_path)

    # 自检：确认 "iphone" 不再是 [UNK]
    probe = wordpiece.encode("iPhone 测试").ids
    if 100 in probe:
        raise RuntimeError(
            "分词器词表仍不完整（含 [UNK]）。请检查 get_vocab() 是否包含 Latin token。"
        )

    meta = {
        "model": model_name,
        "dim": dim,
        "onnx": "bge_small_zh.onnx",
        "tokenizer": "tokenizer.json",
        "pooling": "cls",
        "normalize": "l2",
        "source": source,
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    onnx_size = os.path.getsize(onnx_path) / 1024 / 1024
    print(f"[export] source={source} dim={dim} onnx={onnx_path} ({onnx_size:.1f} MB) tokenizer={tok_path}")
    print(f"[export] vocab_size={len(vocab)} (iphone={vocab.get('iphone')})")
    return meta


def main() -> int:
    parser = argparse.ArgumentParser(description="导出 bge ONNX + tokenizer 工件")
    parser.add_argument("--model", default="BAAI/bge-small-zh-v1.5")
    parser.add_argument(
        "--out-dir",
        default=os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "backend", "xianyu_hunter", "resources", "embedding",
        ),
    )
    args = parser.parse_args()

    export(args.model, os.path.abspath(args.out_dir))
    print("[export] 完成。构建时 build-exe.ps1 会将该目录复制到 release/xianyu-hunter/resources/embedding/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
