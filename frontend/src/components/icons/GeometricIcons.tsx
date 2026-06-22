/**
 * Geometric Essence 图标集
 *
 * 算法艺术哲学：功能即形式 —— 每个图标是其概念的几何纯化表达
 * 设计 token：圆角 R=size*0.12, 线宽 stroke=size*0.06
 * 配色围绕品牌橙 #FF6200 向四个语义方向衍生
 */
import React from 'react'

/* ─── 共享类型 ─── */
interface IconProps {
  size?: number
  className?: string
}

/* ══════════════════════════════════════
   1. 任务创建 — TaskCreationIcon
   概念：从无到有的书写动作
   色调：暖橙 #FF6200 → #FF8533
   几何：文档 + 动态笔触 + 墨迹扩散
   ══════════════════════════════════════ */
export const TaskCreationIcon: React.FC<IconProps> = ({ size = 48, className }) => {
  const s = size
  // 设计 token（与尺寸成比例）
  const stroke = s * 0.055
  const r = s * 0.1

  return (
    <svg width={s} height={s} viewBox="0 0 48 48" fill="none" className={className} xmlns="http://www.w3.org/2000/svg">
      <defs>
        {/* 文档纸张渐变 —— 从左上到右下的微暖色调 */}
        <linearGradient id="taskPaper" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#FFF7ED" />
          <stop offset="100%" stopColor="#FFEDD5" />
        </linearGradient>
        {/* 笔身渐变 —— 深橙到亮橙 */}
        <linearGradient id="taskPen" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#EA580C" />
          <stop offset="100%" stopColor="#FF6200" />
        </linearGradient>
        {/* 笔尖金属光泽 */}
        <linearGradient id="taskTip" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#FBBF24" />
          <stop offset="100%" stopColor="#D97706" />
        </linearGradient>
        {/* 墨迹发光 */}
        <radialGradient id="taskInkGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#FF6200" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#FF6200" stopOpacity="0" />
        </radialGradient>
        {/* 阴影 */}
        <filter id="taskShadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="1.5" stdDeviation="2" floodColor="#FF6200" floodOpacity="0.15" />
        </filter>
      </defs>

      {/* 文档底纸 —— 圆角矩形带折角 */}
      <rect x="8" y="5" width="28" height="36" rx={r} ry={r}
        fill="url(#taskPaper)" stroke="#FDBA74" strokeWidth={stroke * 0.8}
        filter="url(#taskShadow)" />
      {/* 折角效果 */}
      <path d="M28 5 L36 5 L36 13 Z" fill="#FED7AA" stroke="#FDBA74" strokeWidth={stroke * 0.6} />
      <path d="M28 5 L28 13 L36 13" fill="none" stroke="#FDBA74" strokeWidth={stroke * 0.6} />

      {/* 文字行暗示 —— 三条横线表示内容 */}
      <line x1="13" y1="17" x2="30" y2="17" stroke="#FDBA74" strokeWidth={stroke * 0.5} strokeLinecap="round" opacity="0.8" />
      <line x1="13" y1="23" x2="26" y2="23" stroke="#FDBA74" strokeWidth={stroke * 0.5} strokeLinecap="round" opacity="0.5" />
      <line x1="13" y1="29" x2="22" y2="29" stroke="#FDBA74" strokeWidth={stroke * 0.5} strokeLinecap="round" opacity="0.3" />

      {/* 动态笔触 —— 45° 角倾斜的笔，表现书写中的能量 */}
      <g transform="rotate(-35, 32, 32)">
        {/* 笔身 */}
        <rect x="23" y="27" width="4" height="16" rx="1.5" fill="url(#taskPen)" />
        {/* 笔尖锥体 */}
        <path d="M23.5 43 L25 48 L26.5 43 Z" fill="url(#taskTip)" />
        {/* 笔夹装饰线 */}
        <rect x="23.2" y="31" width="3.6" height="1.5" rx="0.7" fill="#FFF" opacity="0.3" />
        {/* 高光点 —— 曲率最大处 */}
        <circle cx="25" cy="29" r="0.8" fill="#FFF" opacity="0.5" />
      </g>

      {/* 墨迹扩散效果 —— 笔尖处的动态墨点 */}
      <circle cx="33" cy="42" r="4" fill="url(#taskInkGlow)" />
      <circle cx="33" cy="42" r="1.5" fill="#FF6200" opacity="0.6" />

      {/* ✨ 星芒装饰 —— 右上角的小闪光，暗示「创建」的新生感 */}
      <g transform="translate(38, 10)" opacity="0.7">
        <line x1="0" y1="-3.5" x2="0" y2="3.5" stroke="#FF6200" strokeWidth="1.2" strokeLinecap="round" />
        <line x1="-3.5" y1="0" x2="3.5" y2="0" stroke="#FF6200" strokeWidth="1.2" strokeLinecap="round" />
      </g>
    </svg>
  )
}

/* ══════════════════════════════════════
   2. 价格策略 — PriceStrategyIcon
   概念：价值的容器与流动
   色调：琥珀金 #D97706 → #F59E0B
   几何：金币/钱袋 + 斐波那契曲线 + 策略边界
   ══════════════════════════════════════ */
export const PriceStrategyIcon: React.FC<IconProps> = ({ size = 48, className }) => {
  const s = size
  const stroke = s * 0.055
  const r = s * 0.1

  return (
    <svg width={s} height={s} viewBox="0 0 48 48" fill="none" className={className} xmlns="http://www.w3.org/2000/svg">
      <defs>
        {/* 金币主体渐变 —— 金属质感 */}
        <linearGradient id="coinBody" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#FEF3C7" />
          <stop offset="40%" stopColor="#FCD34D" />
          <stop offset="70%" stopColor="#F59E0B" />
          <stop offset="100%" stopColor="#D97706" />
        </linearGradient>
        {/* 金币边缘高光 */}
        <linearGradient id="coinRim" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#FBBF24" />
          <stop offset="50%" stopColor="#D97706" />
          <stop offset="100%" stopColor="#B45309" />
        </linearGradient>
        {/* ¥ 符号渐变 */}
        <linearGradient id="yenGrad" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#92400E" />
          <stop offset="100%" stopColor="#78350F" />
        </linearGradient>
        {/* 发光晕染 */}
        <radialGradient id="coinGlow" cx="45%" cy="40%" r="55%">
          <stop offset="0%" stopColor="#FDE68A" stopOpacity="0.5" />
          <stop offset="70%" stopColor="#F59E0B" stopOpacity="0.15" />
          <stop offset="100%" stopColor="#D97706" stopOpacity="0" />
        </radialGradient>
        {/* 策略弧线渐变 */}
        <linearGradient id="strategyArc" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#10B981" stopOpacity="0" />
          <stop offset="50%" stopColor="#10B981" stopOpacity="0.8" />
          <stop offset="100%" stopColor="#10B981" stopOpacity="0" />
        </linearGradient>
        <filter id="coinShadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="2" stdDeviation="2.5" floodColor="#D97706" floodOpacity="0.25" />
        </filter>
      </defs>

      {/* 外层策略弧线 —— 表达「策略」的边界感 */}
      <path d="M8 38 Q24 44 40 34" fill="none" stroke="url(#strategyArc)" strokeWidth={stroke * 0.7}
        strokeLinecap="round" strokeDasharray="3 3" opacity="0.6" />
      <path d="M10 41 Q24 46 38 39" fill="none" stroke="url(#strategyArc)" strokeWidth={stroke * 0.4}
        strokeLinecap="round" strokeDasharray="2 4" opacity="0.3" />

      {/* 金币主体 —— 圆形带内圈纹理 */}
      <circle cx="24" cy="23" r="14" fill="url(#coinGlow)" filter="url(#coinShadow)" />
      <circle cx="24" cy="23" r="14" fill="url(#coinBody)" stroke="url(#coinRim)" strokeWidth={stroke * 1.2} />
      {/* 内圈装饰齿纹（简化为虚线圆） */}
      <circle cx="24" cy="23" r="11" fill="none" stroke="#D97706"
        strokeWidth={stroke * 0.3} strokeDasharray="1.5 2.5" opacity="0.4" />

      {/* ¥ 符号 —— 居中，粗体风格 */}
      <text x="24" y="27.5" textAnchor="middle" fontSize="16" fontWeight="700"
        fill="url(#yenGrad)" fontFamily="system-ui, -apple-system, sans-serif">¥</text>

      /* 金币高光反射点 —— 左上 11 点钟位置 */
      <ellipse cx="17.5" cy="16.5" rx="4" ry="2.5" fill="#FFF" opacity="0.35"
        transform="rotate(-30, 17.5, 16.5)" />

      {/* ↑↑ 上升箭头 —— 表达「增长/优化」的策略意图 */}
      <g transform="translate(35, 12)">
        <path d="M0 7 L0 0 M-3.5 3.5 L0 0 L3.5 3.5" fill="none"
          stroke="#10B981" strokeWidth={stroke * 1.1} strokeLinecap="round" strokeLinejoin="round" />
      </g>

      {/* ✨ 小星芒 */}
      <g transform="translate(11, 11)" opacity="0.5">
        <line x1="0" y1="-2.5" x2="0" y2="2.5" stroke="#F59E0B" strokeWidth="1" strokeLinecap="round" />
        <line x1="-2.5" y1="0" x2="2.5" y2="0" stroke="#F59E0B" strokeWidth="1" strokeLinecap="round" />
      </g>
    </svg>
  )
}

/* ══════════════════════════════════════
   3. 评估规则 — EvalRulesIcon
   概念：度量与判定、精确的防护
   色调：靛蓝 guard #4F46E5 → #6366F1
   几何：盾牌 + 同心靶心 + 刻度线
   ══════════════════════════════════════ */
export const EvalRulesIcon: React.FC<IconProps> = ({ size = 48, className }) => {
  const s = size
  const stroke = s * 0.055
  const r = s * 0.08

  return (
    <svg width={s} height={s} viewBox="0 0 48 48" fill="none" className={className} xmlns="http://www.w3.org/2000/svg">
      <defs>
        {/* 盾牌主体渐变 —— 深靛到浅紫 */}
        <linearGradient id="shieldBody" x1="50%" y1="0%" x2="50%" y2="100%">
          <stop offset="0%" stopColor="#818CF8" />
          <stop offset="60%" stopColor="#6366F1" />
          <stop offset="100%" stopColor="#4F46E5" />
        </linearGradient>
        {/* 盾牌边缘高光 */}
        <linearGradient id="shieldRim" x1="50%" y1="0%" x2="50%" y2="100%">
          <stop offset="0%" stopColor="#A5B4FC" />
          <stop offset="100%" stopColor="#3730A3" />
        </linearGradient>
        {/* 靶心红点渐变 */}
        <radialGradient id="targetRed" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#FCA5A5" />
          <stop offset="60%" stopColor="#EF4444" />
          <stop offset="100%" stopColor="#DC2626" />
        </radialGradient>
        {/* 刻度线渐变 */}
        <linearGradient id="tickGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#C7D2FE" stopOpacity="0.8" />
          <stop offset="100%" stopColor="#A5B4FC" stopOpacity="0.3" />
        </linearGradient>
        <filter id="shieldShadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="2" stdDeviation="2.5" floodColor="#4F46E5" floodOpacity="0.2" />
        </filter>
        {/* 对勾勾选标记渐变 */}
        <linearGradient id="checkGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#34D399" />
          <stop offset="100%" stopColor="#10B981" />
        </linearGradient>
      </defs>

      {/* 盾牌轮廓 —— 经典盾形，上宽下收 */}
      <path
        d={`M24 4 L38 10 Q39 11 39 13 L39 26 Q39 36 24 43 Q9 36 9 26 L9 13 Q9 11 10 10 Z`}
        fill="url(#shieldBody)" stroke="url(#shieldRim)" strokeWidth={stroke * 1.1}
        filter="url(#shieldShadow)"
      />

      {/* 内部靶心系统 —— 同心圆表达「精确度量」 */}
      <circle cx="24" cy="24" r="10" fill="none" stroke="#C7D2FE" strokeWidth={stroke * 0.35} opacity="0.5" />
      <circle cx="24" cy="24" r="7" fill="none" stroke="#A5B4FC" strokeWidth={stroke * 0.45} opacity="0.6" />
      <circle cx="24" cy="24" r="4" fill="none" stroke="#818CF8" strokeWidth={stroke * 0.5} opacity="0.7" />
      {/* 靶心红点 */}
      <circle cx="24" cy="24" r="2" fill="url(#targetRed)" />

      {/* 十字准星 —— 强调「精准判定」 */}
      <line x1="24" y1="18" x2="24" y2="21" stroke="#EF4444" strokeWidth={stroke * 0.4} strokeLinecap="round" opacity="0.6" />
      <line x1="24" y1="27" x2="24" y2="30" stroke="#EF4444" strokeWidth={stroke * 0.4} strokeLinecap="round" opacity="0.6" />
      <line x1="18" y1="24" x2="21" y2="24" stroke="#EF4444" strokeWidth={stroke * 0.4} strokeLinecap="round" opacity="0.6" />
      <line x1="27" y1="24" x2="30" y2="24" stroke="#EF4444" strokeWidth={stroke * 0.4} strokeLinecap="round" opacity="0.6" />

      {/* 刻度线 —— 盾牌内圈的度量刻度（8 方位） */}
      {[
        { x: 24, y: 13.5, angle: 0 },
        { x: 31.2, y: 16.8, angle: 45 },
        { x: 34.5, y: 24, angle: 90 },
        { x: 31.2, y: 31.2, angle: 135 },
        { x: 24, y: 34.5, angle: 180 },
        { x: 16.8, y: 31.2, angle: 225 },
        { x: 13.5, y: 24, angle: 270 },
        { x: 16.8, y: 16.8, angle: 315 },
      ].map((tick, i) => (
        <line key={i} x1={tick.x} y1={tick.y}
          x2={24 + (tick.x - 24) * 0.82} y2={24 + (tick.y - 24) * 0.82}
          stroke="url(#tickGrad)" strokeWidth={stroke * 0.4} strokeLinecap="round" />
      ))}

      {/* ✓ 通过标记 —— 右下角的绿色对勾 */}
      <g transform="translate(30, 32) scale(0.65)">
        <circle cx="0" cy="0" r="7" fill="#ECFDF5" opacity="0.9" />
        <path d="M-3.5 0 L-1 2.5 L4 -3" fill="none" stroke="url(#checkGrad)"
          strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" />
      </g>

      {/* 高光 —— 左上盾牌边缘反光 */}
      <path d="M24 4 L38 10 Q39 11 39 13 L39 15 Q39 13 38 12 L24 6 L10 12 Q9 13 9 15 L9 13 Q9 11 10 10 Z"
        fill="#FFF" opacity="0.15" />
    </svg>
  )
}

/* ══════════════════════════════════════
   4. 通知渠道 — NotifierChannelsIcon
   概念：信号的辐射传播
   色调：珊瑚 alert #F43F5E → #FB7185
   几何：铃铛 + 阻尼波前 + 信号粒子
   ══════════════════════════════════════ */
export const NotifierChannelsIcon: React.FC<IconProps> = ({ size = 48, className }) => {
  const s = size
  const stroke = s * 0.055
  const r = s * 0.12

  return (
    <svg width={s} height={s} viewBox="0 0 48 48" fill="none" className={className} xmlns="http://www.w3.org/2000/svg">
      <defs>
        {/* 铃铛主体渐变 */}
        <linearGradient id="bellBody" x1="50%" y1="0%" x2="50%" y2="100%">
          <stop offset="0%" stopColor="#FDA4AF" />
          <stop offset="45%" stopColor="#F43F5E" />
          <stop offset="100%" stopColor="#BE123C" />
        </linearGradient>
        {/* 铃铛高光边 */}
        <linearGradient id="bellHighlight" x1="50%" y1="0%" x2="50%" y2="100%">
          <stop offset="0%" stopColor="#FECDD3" />
          <stop offset="100%" stopColor="#E11D48" />
        </linearGradient>
        {/* 波前渐变 —— 从内到外衰减 */}
        <radialGradient id="waveGrad1" cx="50%" cy="58%" r="50%">
          <stop offset="0%" stopColor="#F43F5E" stopOpacity="0.5" />
          <stop offset="100%" stopColor="#F43F5E" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="waveGrad2" cx="50%" cy="58%" r="50%">
          <stop offset="0%" stopColor="#F43F5E" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#F43F5E" stopOpacity="0" />
        </radialGradient>
        {/* 底座渐变 */}
        <linearGradient id="bellBase" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#FDA4AF" />
          <stop offset="100%" stopColor="#BE123C" />
        </linearGradient>
        {/* 撞击点发光 */}
        <radialGradient id="strikeGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#FEF08A" stopOpacity="0.8" />
          <stop offset="50%" stopColor="#F43F5E" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#F43F5E" stopOpacity="0" />
        </radialGradient>
        <filter id="bellShadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="2" stdDeviation="2" floodColor="#F43F5E" floodOpacity="0.2" />
        </filter>
      </defs>

      {/* 扩散波前（后层）—— 表达信号传播 */}
      <path d="M10 34 Q10 21 19 17" fill="none" stroke="url(#waveGrad2)" strokeWidth={stroke * 0.6}
        strokeLinecap="round" opacity="0.5" />
      <path d="M6 36 Q6 19 17 14" fill="none" stroke="url(#waveGrad1)" strokeWidth={stroke * 0.5}
        strokeLinecap="round" opacity="0.35" />

      {/* 铃铛主体 —— 经典钟形轮廓 */}
      <g filter="url(#bellShadow)">
        {/* 铃铛外廓 */}
        <path
          d={`M16 28 L16 20 Q16 12 24 12 Q32 12 32 20 L32 28 Q32 32 28 34 L20 34 Q16 32 16 28 Z`}
          fill="url(#bellBody)" stroke="url(#bellHighlight)" strokeWidth={stroke * 1}
        />
        {/* 铃铛顶部提环 */}
        <path d="M21 12 Q21 8 24 8 Q27 8 27 12" fill="none"
          stroke="url(#bellHighlight)" strokeWidth={stroke * 1.3} strokeLinecap="round" />
        {/* 铃铛底部底座 */}
        <rect x="19" y="34" width="10" height="3" rx={r * 0.5} fill="url(#bellBase)" />
        {/* 铃舌（内部撞击小球） */}
        <circle cx="24" cy="31" r="2.2" fill="#FECDD3" stroke="#E11D48" strokeWidth={stroke * 0.4} />
      </g>

      {/* 扩散波前（前层）—— 右侧主波 */}
      <path d="M34 28 Q42 28 42 20" fill="none" stroke="#F43F5E" strokeWidth={stroke * 0.8}
        strokeLinecap="round" opacity="0.6" />
      <path d="M37 25 Q44 25 44 17" fill="none" stroke="#F43F5E" strokeWidth={stroke * 0.5}
        strokeLinecap="round" opacity="0.35" />

      {/* 撞击点发光效果 —— 铃铛右侧 */}
      <circle cx="34" cy="22" r="5" fill="url(#strikeGlow)" />
      <circle cx="34" cy="22" r="1.5" fill="#FEF08A" opacity="0.7" />

      {/* 高光 —— 铃铛左上曲面反光 */}
      <path d="M18 20 Q18 15 24 14 Q22 15 22 20 L22 26 Q18 25 18 20 Z"
        fill="#FFF" opacity="0.12" />

      {/* 🔔 信号粒子 —— 波前上的小点表示传播中 */}
      <circle cx="39" cy="19" r="1" fill="#F43F5E" opacity="0.6" />
      <circle cx="42.5" cy="15.5" r="0.7" fill="#F43F5E" opacity="0.35" />
      <circle cx="7" cy="33" r="0.8" fill="#F43F5E" opacity="0.3" />
    </svg>
  )
}

/* ══════════════════════════════════════
   5. AI 服务配置 — AIConfigIcon
   概念：智能神经网络的运算核心
   色调：紫罗兰 #8B5CF6 → #A78BFA
   几何：芯片载体 + 神经节点 + 突触连线
   ══════════════════════════════════════ */
export const AIConfigIcon: React.FC<IconProps> = ({ size = 48, className }) => {
  const s = size
  const stroke = s * 0.055
  const r = s * 0.1

  return (
    <svg width={s} height={s} viewBox="0 0 48 48" fill="none" className={className} xmlns="http://www.w3.org/2000/svg">
      <defs>
        {/* 芯片主体渐变 */}
        <linearGradient id="chipBody" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#EDE9FE" />
          <stop offset="50%" stopColor="#C4B5FD" />
          <stop offset="100%" stopColor="#8B5CF6" />
        </linearGradient>
        {/* 芯片边缘 */}
        <linearGradient id="chipRim" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#A78BFA" />
          <stop offset="100%" stopColor="#6D28D9" />
        </linearGradient>
        {/* 神经节点发光 */}
        <radialGradient id="neuronGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#F5F3FF" stopOpacity="0.9" />
          <stop offset="60%" stopColor="#A78BFA" stopOpacity="0.4" />
          <stop offset="100%" stopColor="#8B5CF6" stopOpacity="0" />
        </radialGradient>
        {/* 突触连线渐变 */}
        <linearGradient id="synapse" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#C4B5FD" stopOpacity="0.8" />
          <stop offset="100%" stopColor="#7C3AED" stopOpacity="0.4" />
        </linearGradient>
        <filter id="chipShadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="2" stdDeviation="2.5" floodColor="#8B5CF6" floodOpacity="0.25" />
        </filter>
      </defs>

      {/* 芯片载体 —— 圆角方形 */}
      <rect x="10" y="10" width="28" height="28" rx={r} fill="url(#chipBody)"
        stroke="url(#chipRim)" strokeWidth={stroke * 1.1} filter="url(#chipShadow)" />

      {/* 芯片引脚 —— 四边各 3 个 */}
      {/* 上边 */}
      {[16, 24, 32].map((x, i) => (
        <line key={`u${i}`} x1={x} y1="10" x2={x} y2="6" stroke="#7C3AED" strokeWidth={stroke * 0.6} strokeLinecap="round" />
      ))}
      {/* 下边 */}
      {[16, 24, 32].map((x, i) => (
        <line key={`d${i}`} x1={x} y1="38" x2={x} y2="42" stroke="#7C3AED" strokeWidth={stroke * 0.6} strokeLinecap="round" />
      ))}
      {/* 左边 */}
      {[16, 24, 32].map((y, i) => (
        <line key={`l${i}`} x1="10" y1={y} x2="6" y2={y} stroke="#7C3AED" strokeWidth={stroke * 0.6} strokeLinecap="round" />
      ))}
      {/* 右边 */}
      {[16, 24, 32].map((y, i) => (
        <line key={`r${i}`} x1="38" y1={y} x2="42" y2={y} stroke="#7C3AED" strokeWidth={stroke * 0.6} strokeLinecap="round" />
      ))}

      {/* 神经网络节点 —— 三层拓扑 */}
      {/* 输入层（左） */}
      <circle cx="17" cy="18" r="2" fill="url(#neuronGlow)" stroke="#7C3AED" strokeWidth={stroke * 0.3} />
      <circle cx="17" cy="30" r="2" fill="url(#neuronGlow)" stroke="#7C3AED" strokeWidth={stroke * 0.3} />
      {/* 隐藏层（中） */}
      <circle cx="24" cy="15" r="2.2" fill="url(#neuronGlow)" stroke="#7C3AED" strokeWidth={stroke * 0.3} />
      <circle cx="24" cy="24" r="2.5" fill="url(#neuronGlow)" stroke="#6D28D9" strokeWidth={stroke * 0.4} />
      <circle cx="24" cy="33" r="2.2" fill="url(#neuronGlow)" stroke="#7C3AED" strokeWidth={stroke * 0.3} />
      {/* 输出层（右） */}
      <circle cx="31" cy="20" r="2" fill="url(#neuronGlow)" stroke="#7C3AED" strokeWidth={stroke * 0.3} />
      <circle cx="31" cy="28" r="2" fill="url(#neuronGlow)" stroke="#7C3AED" strokeWidth={stroke * 0.3} />

      {/* 突触连线 —— 输入层到隐藏层 */}
      <line x1="17" y1="18" x2="24" y2="15" stroke="url(#synapse)" strokeWidth={stroke * 0.35} />
      <line x1="17" y1="18" x2="24" y2="24" stroke="url(#synapse)" strokeWidth={stroke * 0.35} />
      <line x1="17" y1="30" x2="24" y2="24" stroke="url(#synapse)" strokeWidth={stroke * 0.35} />
      <line x1="17" y1="30" x2="24" y2="33" stroke="url(#synapse)" strokeWidth={stroke * 0.35} />
      {/* 突触连线 —— 隐藏层到输出层 */}
      <line x1="24" y1="15" x2="31" y2="20" stroke="url(#synapse)" strokeWidth={stroke * 0.35} />
      <line x1="24" y1="24" x2="31" y2="20" stroke="url(#synapse)" strokeWidth={stroke * 0.35} />
      <line x1="24" y1="24" x2="31" y2="28" stroke="url(#synapse)" strokeWidth={stroke * 0.35} />
      <line x1="24" y1="33" x2="31" y2="28" stroke="url(#synapse)" strokeWidth={stroke * 0.35} />

      {/* 中心节点脉冲光环 */}
      <circle cx="24" cy="24" r="5" fill="none" stroke="#A78BFA" strokeWidth={stroke * 0.2} opacity="0.3" />
      <circle cx="24" cy="24" r="7" fill="none" stroke="#A78BFA" strokeWidth={stroke * 0.15} opacity="0.15" />

      {/* 高光 —— 芯片左上角反光 */}
      <path d="M10 10 L28 10 Q20 12 12 20 L10 28 Z" fill="#FFF" opacity="0.12" />
    </svg>
  )
}

/* ══════════════════════════════════════
   6. 抢单策略 — BuyerStrategyIcon
   概念：极速抢占的瞬时爆发
   色调：炽红 #EF4444 → #F97316
   几何：闪电 + 目标准星 + 速度线
   ══════════════════════════════════════ */
export const BuyerStrategyIcon: React.FC<IconProps> = ({ size = 48, className }) => {
  const s = size
  const stroke = s * 0.055
  const r = s * 0.1

  return (
    <svg width={s} height={s} viewBox="0 0 48 48" fill="none" className={className} xmlns="http://www.w3.org/2000/svg">
      <defs>
        {/* 闪电主体渐变 */}
        <linearGradient id="boltBody" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#FED7AA" />
          <stop offset="40%" stopColor="#FB923C" />
          <stop offset="70%" stopColor="#F97316" />
          <stop offset="100%" stopColor="#EA580C" />
        </linearGradient>
        {/* 闪电边缘高光 */}
        <linearGradient id="boltEdge" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#FFEDD5" />
          <stop offset="100%" stopColor="#C2410C" />
        </linearGradient>
        {/* 目标准星渐变 */}
        <radialGradient id="targetRing" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#EF4444" stopOpacity="0" />
          <stop offset="70%" stopColor="#EF4444" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#DC2626" stopOpacity="0" />
        </radialGradient>
        {/* 速度线渐变 */}
        <linearGradient id="speedLine" x1="100%" y1="0%" x2="0%" y2="0%">
          <stop offset="0%" stopColor="#F97316" stopOpacity="0.8" />
          <stop offset="100%" stopColor="#F97316" stopOpacity="0" />
        </linearGradient>
        <filter id="boltShadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="2" stdDeviation="2.5" floodColor="#EA580C" floodOpacity="0.3" />
        </filter>
      </defs>

      {/* 目标准星 —— 背景同心圆 */}
      <circle cx="30" cy="18" r="12" fill="url(#targetRing)" />
      <circle cx="30" cy="18" r="10" fill="none" stroke="#EF4444" strokeWidth={stroke * 0.3} opacity="0.3" strokeDasharray="2 3" />
      <circle cx="30" cy="18" r="7" fill="none" stroke="#EF4444" strokeWidth={stroke * 0.25} opacity="0.2" />

      {/* 速度线 —— 左侧拖尾 */}
      <path d="M4 30 Q12 28 20 30" fill="none" stroke="url(#speedLine)" strokeWidth={stroke * 0.8} strokeLinecap="round" />
      <path d="M6 36 Q14 34 22 36" fill="none" stroke="url(#speedLine)" strokeWidth={stroke * 0.5} strokeLinecap="round" opacity="0.6" />
      <path d="M8 24 Q14 22 20 24" fill="none" stroke="url(#speedLine)" strokeWidth={stroke * 0.4} strokeLinecap="round" opacity="0.4" />

      {/* 闪电主体 —— 经典 Z 字形 */}
      <g filter="url(#boltShadow)">
        <path
          d="M26 4 L14 22 L22 22 L18 40 L34 20 L26 20 Z"
          fill="url(#boltBody)" stroke="url(#boltEdge)" strokeWidth={stroke * 0.8}
          strokeLinejoin="round"
        />
      </g>

      {/* 闪电核心高光 —— 内部亮线 */}
      <path d="M25 8 L18 20 L23 20 L21 32" fill="none" stroke="#FFF" strokeWidth={stroke * 0.3}
        strokeLinecap="round" opacity="0.4" />

      {/* 火花粒子 —— 闪电尖端 */}
      <circle cx="18" cy="40" r="1.5" fill="#FBBF24" opacity="0.8" />
      <circle cx="15" cy="37" r="0.8" fill="#F97316" opacity="0.5" />
      <circle cx="21" cy="42" r="0.6" fill="#EF4444" opacity="0.4" />

      {/* 闪电顶部能量点 */}
      <circle cx="26" cy="4" r="2" fill="#FEF3C7" opacity="0.6" />
    </svg>
  )
}

/* ══════════════════════════════════════
   7. 搜索参数 — SearchConfigIcon
   概念：精准过滤与发现
   色调：青蓝 #06B6D4 → #22D3EE
   几何：放大镜 + 筛选漏斗 + 参数刻度
   ══════════════════════════════════════ */
export const SearchConfigIcon: React.FC<IconProps> = ({ size = 48, className }) => {
  const s = size
  const stroke = s * 0.055
  const r = s * 0.1

  return (
    <svg width={s} height={s} viewBox="0 0 48 48" fill="none" className={className} xmlns="http://www.w3.org/2000/svg">
      <defs>
        {/* 放大镜镜片渐变 */}
        <radialGradient id="lensGlass" cx="40%" cy="35%" r="65%">
          <stop offset="0%" stopColor="#CFFAFE" stopOpacity="0.8" />
          <stop offset="60%" stopColor="#67E8F9" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#06B6D4" stopOpacity="0.15" />
        </radialGradient>
        {/* 镜框渐变 */}
        <linearGradient id="lensFrame" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#22D3EE" />
          <stop offset="100%" stopColor="#0891B2" />
        </linearGradient>
        {/* 手柄渐变 */}
        <linearGradient id="lensHandle" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#06B6D4" />
          <stop offset="100%" stopColor="#0E7490" />
        </linearGradient>
        {/* 筛选漏斗渐变 */}
        <linearGradient id="funnelGrad" x1="50%" y1="0%" x2="50%" y2="100%">
          <stop offset="0%" stopColor="#A5F3FC" stopOpacity="0.7" />
          <stop offset="100%" stopColor="#22D3EE" stopOpacity="0.3" />
        </linearGradient>
        <filter id="lensShadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="2" stdDeviation="2" floodColor="#06B6D4" floodOpacity="0.2" />
        </filter>
      </defs>

      {/* 放大镜主体 */}
      <g filter="url(#lensShadow)">
        {/* 镜片玻璃 */}
        <circle cx="20" cy="20" r="12" fill="url(#lensGlass)" stroke="url(#lensFrame)" strokeWidth={stroke * 1.2} />
        {/* 镜片内圈反光 */}
        <circle cx="20" cy="20" r="9" fill="none" stroke="#67E8F9" strokeWidth={stroke * 0.2} opacity="0.4" />
        {/* 手柄 */}
        <line x1="29" y1="29" x2="40" y2="40" stroke="url(#lensHandle)" strokeWidth={stroke * 2} strokeLinecap="round" />
        {/* 手柄端点 */}
        <circle cx="40" cy="40" r="2" fill="#0E7490" />
      </g>

      {/* 镜片内的筛选漏斗 —— 表达「参数过滤」 */}
      <path d="M14 16 L26 16 L22 22 L22 28 L18 28 L18 22 Z"
        fill="url(#funnelGrad)" stroke="#0891B2" strokeWidth={stroke * 0.4} strokeLinejoin="round" />

      {/* 参数刻度线 —— 镜片右侧 */}
      <line x1="15" y1="13" x2="17" y2="13" stroke="#06B6D4" strokeWidth={stroke * 0.4} strokeLinecap="round" opacity="0.6" />
      <line x1="23" y1="13" x2="25" y2="13" stroke="#06B6D4" strokeWidth={stroke * 0.4} strokeLinecap="round" opacity="0.6" />

      {/* 镜片高光 —— 左上反光 */}
      <ellipse cx="15" cy="15" rx="4" ry="2.5" fill="#FFF" opacity="0.3" transform="rotate(-30, 15, 15)" />

      {/* 搜索结果粒子 —— 漏斗下方 */}
      <circle cx="20" cy="32" r="1" fill="#22D3EE" opacity="0.7" />
      <circle cx="18" cy="35" r="0.7" fill="#06B6D4" opacity="0.5" />
      <circle cx="22" cy="35" r="0.7" fill="#06B6D4" opacity="0.5" />
    </svg>
  )
}

/* ══════════════════════════════════════
   8. 配置版本管理 — VersionManagerIcon
   概念：时间线上的版本演进
   色调：青绿 #14B8A6 → #2DD4BF
   几何：时间线 + 版本节点 + 分支
   ══════════════════════════════════════ */
export const VersionManagerIcon: React.FC<IconProps> = ({ size = 48, className }) => {
  const s = size
  const stroke = s * 0.055
  const r = s * 0.1

  return (
    <svg width={s} height={s} viewBox="0 0 48 48" fill="none" className={className} xmlns="http://www.w3.org/2000/svg">
      <defs>
        {/* 时间线主干渐变 */}
        <linearGradient id="timeline" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#5EEAD4" />
          <stop offset="50%" stopColor="#2DD4BF" />
          <stop offset="100%" stopColor="#14B8A6" />
        </linearGradient>
        {/* 版本节点渐变 */}
        <radialGradient id="versionNode" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#CCFBF1" />
          <stop offset="60%" stopColor="#2DD4BF" />
          <stop offset="100%" stopColor="#0F766E" />
        </radialGradient>
        {/* 当前版本高亮 */}
        <radialGradient id="currentVersion" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#FDE68A" />
          <stop offset="50%" stopColor="#FBBF24" />
          <stop offset="100%" stopColor="#D97706" />
        </radialGradient>
        {/* 分支线渐变 */}
        <linearGradient id="branchLine" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#2DD4BF" stopOpacity="0.6" />
          <stop offset="100%" stopColor="#2DD4BF" stopOpacity="0.2" />
        </linearGradient>
        <filter id="versionShadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="2" stdDeviation="2" floodColor="#14B8A6" floodOpacity="0.2" />
        </filter>
      </defs>

      {/* 时间线主干 —— 垂直贯穿 */}
      <line x1="16" y1="6" x2="16" y2="42" stroke="url(#timeline)" strokeWidth={stroke * 1.2} strokeLinecap="round" />

      {/* 分支线 —— 右侧延伸 */}
      <path d="M16 14 Q22 14 26 10" fill="none" stroke="url(#branchLine)" strokeWidth={stroke * 0.6} strokeLinecap="round" />
      <path d="M16 28 Q22 28 26 32" fill="none" stroke="url(#branchLine)" strokeWidth={stroke * 0.6} strokeLinecap="round" />

      {/* 版本节点 v1（最早） */}
      <g filter="url(#versionShadow)">
        <circle cx="16" cy="10" r="3.5" fill="url(#versionNode)" stroke="#0F766E" strokeWidth={stroke * 0.4} />
      </g>
      <text x="16" y="11.5" textAnchor="middle" fontSize="4" fontWeight="700" fill="#FFF" fontFamily="system-ui, sans-serif">v1</text>

      {/* 分支节点 */}
      <circle cx="28" cy="10" r="2.5" fill="url(#versionNode)" stroke="#0F766E" strokeWidth={stroke * 0.3} opacity="0.7" />

      {/* 版本节点 v2 */}
      <g filter="url(#versionShadow)">
        <circle cx="16" cy="22" r="3.5" fill="url(#versionNode)" stroke="#0F766E" strokeWidth={stroke * 0.4} />
      </g>
      <text x="16" y="23.5" textAnchor="middle" fontSize="4" fontWeight="700" fill="#FFF" fontFamily="system-ui, sans-serif">v2</text>

      {/* 版本节点 v3（当前版本 —— 金色高亮） */}
      <g filter="url(#versionShadow)">
        <circle cx="16" cy="34" r="4.5" fill="url(#currentVersion)" stroke="#B45309" strokeWidth={stroke * 0.5} />
        {/* 当前版本脉冲环 */}
        <circle cx="16" cy="34" r="7" fill="none" stroke="#FBBF24" strokeWidth={stroke * 0.2} opacity="0.4" />
        <circle cx="16" cy="34" r="9" fill="none" stroke="#FBBF24" strokeWidth={stroke * 0.15} opacity="0.2" />
      </g>
      <text x="16" y="35.5" textAnchor="middle" fontSize="4.5" fontWeight="700" fill="#FFF" fontFamily="system-ui, sans-serif">v3</text>

      {/* 分支节点 */}
      <circle cx="28" cy="32" r="2.5" fill="url(#versionNode)" stroke="#0F766E" strokeWidth={stroke * 0.3} opacity="0.7" />

      {/* 版本标签 —— 右侧 */}
      <text x="34" y="12" fontSize="5" fill="#0F766E" opacity="0.6" fontFamily="system-ui, sans-serif">→</text>
      <text x="34" y="36" fontSize="5" fill="#B45309" opacity="0.8" fontFamily="system-ui, sans-serif">★</text>

      {/* 时间线底部端点 */}
      <circle cx="16" cy="42" r="1.5" fill="#14B8A6" opacity="0.5" />
    </svg>
  )
}

/* ══════════════════════════════════════
   9. 系统清理 — CleanupIcon
   概念：扫除冗余的净化动作
   色调：翠绿 #10B981 → #34D399
   几何：扫帚 + 清理粒子 + 净化波纹
   ══════════════════════════════════════ */
export const CleanupIcon: React.FC<IconProps> = ({ size = 48, className }) => {
  const s = size
  const stroke = s * 0.055
  const r = s * 0.1

  return (
    <svg width={s} height={s} viewBox="0 0 48 48" fill="none" className={className} xmlns="http://www.w3.org/2000/svg">
      <defs>
        {/* 扫帚柄渐变 */}
        <linearGradient id="broomHandle" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#A7F3D0" />
          <stop offset="50%" stopColor="#34D399" />
          <stop offset="100%" stopColor="#059669" />
        </linearGradient>
        {/* 扫帚毛渐变 */}
        <linearGradient id="broomBristles" x1="50%" y1="0%" x2="50%" y2="100%">
          <stop offset="0%" stopColor="#6EE7B7" />
          <stop offset="100%" stopColor="#10B981" />
        </linearGradient>
        {/* 净化波纹 */}
        <radialGradient id="purifyWave" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#34D399" stopOpacity="0.4" />
          <stop offset="100%" stopColor="#10B981" stopOpacity="0" />
        </radialGradient>
        {/* 垃圾粒子渐变 */}
        <linearGradient id="dustParticle" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#FBBF24" />
          <stop offset="100%" stopColor="#D97706" />
        </linearGradient>
        <filter id="broomShadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="2" stdDeviation="2" floodColor="#10B981" floodOpacity="0.2" />
        </filter>
      </defs>

      {/* 净化波纹 —— 扫帚底部扩散 */}
      <ellipse cx="18" cy="38" rx="14" ry="4" fill="url(#purifyWave)" />
      <ellipse cx="18" cy="38" rx="10" ry="3" fill="none" stroke="#34D399" strokeWidth={stroke * 0.2} opacity="0.3" />

      {/* 扫帚柄 —— 斜向手柄 */}
      <g filter="url(#broomShadow)">
        <line x1="30" y1="6" x2="18" y2="30" stroke="url(#broomHandle)" strokeWidth={stroke * 2.2} strokeLinecap="round" />
        {/* 手柄末端球饰 */}
        <circle cx="30" cy="6" r="2.5" fill="url(#broomHandle)" stroke="#059669" strokeWidth={stroke * 0.3} />
      </g>

      {/* 扫帚头 —— 三角形刷毛束 */}
      <path
        d="M10 30 L26 30 L22 40 L14 40 Z"
        fill="url(#broomBristles)" stroke="#059669" strokeWidth={stroke * 0.6} strokeLinejoin="round"
        filter="url(#broomShadow)"
      />

      {/* 扫帚毛纹理 —— 垂直细线 */}
      {[12, 15, 18, 21, 24].map((x, i) => (
        <line key={i} x1={x} y1="30" x2={x + (x - 18) * 0.3} y2="40"
          stroke="#047857" strokeWidth={stroke * 0.2} opacity="0.4" />
      ))}

      {/* 扫帚头部绑带 */}
      <rect x="11" y="28" width="14" height="2.5" rx="1" fill="#059669" opacity="0.8" />

      {/* 清理中的垃圾粒子 —— 被扫起的灰尘 */}
      <circle cx="32" cy="34" r="1.5" fill="url(#dustParticle)" opacity="0.8" />
      <circle cx="36" cy="30" r="1" fill="#FBBF24" opacity="0.6" />
      <circle cx="38" cy="36" r="0.8" fill="#D97706" opacity="0.5" />
      <circle cx="34" cy="40" r="0.6" fill="#92400E" opacity="0.4" />

      {/* 净化粒子 —— 绿色光点表示清洁完成 */}
      <circle cx="8" cy="34" r="1" fill="#34D399" opacity="0.7" />
      <circle cx="6" cy="30" r="0.7" fill="#10B981" opacity="0.5" />

      {/* 扫帚柄高光 */}
      <line x1="29" y1="8" x2="19" y2="28" stroke="#FFF" strokeWidth={stroke * 0.3} strokeLinecap="round" opacity="0.3" />
    </svg>
  )
}

/* ══════════════════════════════════════
   10. 数据库维护 — DatabaseAdminIcon
   概念：数据存储的层叠结构
   色调：天蓝 #3B82F6 → #60A5FA
   几何：数据库圆柱 + 齿轮 + 数据流
   ══════════════════════════════════════ */
export const DatabaseAdminIcon: React.FC<IconProps> = ({ size = 48, className }) => {
  const s = size
  const stroke = s * 0.055
  const r = s * 0.1

  return (
    <svg width={s} height={s} viewBox="0 0 48 48" fill="none" className={className} xmlns="http://www.w3.org/2000/svg">
      <defs>
        {/* 数据库圆柱顶面 */}
        <linearGradient id="dbTop" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#DBEAFE" />
          <stop offset="50%" stopColor="#93C5FD" />
          <stop offset="100%" stopColor="#3B82F6" />
        </linearGradient>
        {/* 数据库圆柱侧面 */}
        <linearGradient id="dbBody" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#60A5FA" />
          <stop offset="50%" stopColor="#3B82F6" />
          <stop offset="100%" stopColor="#1D4ED8" />
        </linearGradient>
        {/* 数据库边缘 */}
        <linearGradient id="dbEdge" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#BFDBFE" />
          <stop offset="100%" stopColor="#1E40AF" />
        </linearGradient>
        {/* 齿轮渐变 */}
        <linearGradient id="gearGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#FCD34D" />
          <stop offset="100%" stopColor="#D97706" />
        </linearGradient>
        {/* 数据流渐变 */}
        <linearGradient id="dataFlow" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#93C5FD" stopOpacity="0.8" />
          <stop offset="100%" stopColor="#3B82F6" stopOpacity="0" />
        </linearGradient>
        <filter id="dbShadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="2" stdDeviation="2.5" floodColor="#3B82F6" floodOpacity="0.25" />
        </filter>
      </defs>

      {/* 数据流 —— 左侧数据流入 */}
      <path d="M2 24 Q10 24 14 24" fill="none" stroke="url(#dataFlow)" strokeWidth={stroke * 0.8} strokeLinecap="round" />
      <circle cx="4" cy="22" r="0.8" fill="#60A5FA" opacity="0.6" />
      <circle cx="7" cy="26" r="0.6" fill="#3B82F6" opacity="0.4" />

      {/* 数据库圆柱主体 */}
      <g filter="url(#dbShadow)">
        {/* 底层圆柱 */}
        <path d="M14 28 L14 38 Q14 42 24 42 Q34 42 34 38 L34 28"
          fill="url(#dbBody)" stroke="url(#dbEdge)" strokeWidth={stroke * 0.8} />
        {/* 中层圆柱 */}
        <path d="M14 18 L14 28 Q14 32 24 32 Q34 32 34 28 L34 18"
          fill="url(#dbBody)" stroke="url(#dbEdge)" strokeWidth={stroke * 0.8} />
        {/* 顶层圆柱 */}
        <path d="M14 8 L14 18 Q14 22 24 22 Q34 22 34 18 L34 8"
          fill="url(#dbBody)" stroke="url(#dbEdge)" strokeWidth={stroke * 0.8} />

        {/* 顶面椭圆 */}
        <ellipse cx="24" cy="8" rx="10" ry="3.5" fill="url(#dbTop)" stroke="url(#dbEdge)" strokeWidth={stroke * 0.6} />
        {/* 中层分隔椭圆 */}
        <ellipse cx="24" cy="18" rx="10" ry="3.5" fill="none" stroke="url(#dbEdge)" strokeWidth={stroke * 0.4} opacity="0.6" />
        {/* 底层分隔椭圆 */}
        <ellipse cx="24" cy="28" rx="10" ry="3.5" fill="none" stroke="url(#dbEdge)" strokeWidth={stroke * 0.4} opacity="0.6" />
      </g>

      {/* 数据库层间数据点 —— 表达存储的数据 */}
      <circle cx="20" cy="14" r="0.8" fill="#DBEAFE" opacity="0.8" />
      <circle cx="24" cy="13" r="0.6" fill="#BFDBFE" opacity="0.6" />
      <circle cx="28" cy="14" r="0.8" fill="#DBEAFE" opacity="0.8" />

      <circle cx="20" cy="24" r="0.8" fill="#DBEAFE" opacity="0.8" />
      <circle cx="28" cy="24" r="0.8" fill="#DBEAFE" opacity="0.8" />

      <circle cx="22" cy="34" r="0.6" fill="#BFDBFE" opacity="0.6" />
      <circle cx="26" cy="34" r="0.6" fill="#BFDBFE" opacity="0.6" />

      {/* 维护齿轮 —— 右下角 */}
      <g transform="translate(36, 36)">
        {/* 齿轮齿 */}
        {[0, 45, 90, 135, 180, 225, 270, 315].map((angle, i) => {
          const rad = (angle * Math.PI) / 180
          const x1 = Math.cos(rad) * 4
          const y1 = Math.sin(rad) * 4
          const x2 = Math.cos(rad) * 6
          const y2 = Math.sin(rad) * 6
          return (
            <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
              stroke="url(#gearGrad)" strokeWidth={stroke * 0.8} strokeLinecap="round" />
          )
        })}
        {/* 齿轮主体 */}
        <circle cx="0" cy="0" r="4" fill="url(#gearGrad)" stroke="#92400E" strokeWidth={stroke * 0.3} />
        {/* 齿轮中心孔 */}
        <circle cx="0" cy="0" r="1.5" fill="#FEF3C7" stroke="#D97706" strokeWidth={stroke * 0.2} />
      </g>

      {/* 顶面高光 */}
      <ellipse cx="20" cy="7" rx="4" ry="1.5" fill="#FFF" opacity="0.3" />
    </svg>
  )
}

/* ══════════════════════════════════════
   统一导出 & QuickEntryIcon 组合组件
   ══════════════════════════════════════ */

/** 快捷入口图标映射表 —— key 与 Dashboard 卡片一一对应 */
export const QUICK_ENTRY_ICONS: Record<string, React.FC<IconProps>> = {
  task: TaskCreationIcon,
  price: PriceStrategyIcon,
  eval: EvalRulesIcon,
  notifier: NotifierChannelsIcon,
  ai: AIConfigIcon,
  buyer: BuyerStrategyIcon,
  search: SearchConfigIcon,
  version: VersionManagerIcon,
  cleanup: CleanupIcon,
  dbAdmin: DatabaseAdminIcon,
}

/**
 * QuickEntryIcon —— 根据类型返回对应图标的便捷包装
 * 用法：<QuickEntryIcon type="task" size={48} />
 */
interface QuickEntryIconProps extends IconProps {
  type: 'task' | 'price' | 'eval' | 'notifier' | 'ai' | 'buyer' | 'search' | 'version' | 'cleanup' | 'dbAdmin'
}

export const QuickEntryIcon: React.FC<QuickEntryIconProps> = ({ type, ...rest }) => {
  const IconComponent = QUICK_ENTRY_ICONS[type]
  if (!IconComponent) return null
  return <IconComponent {...rest} />
}
