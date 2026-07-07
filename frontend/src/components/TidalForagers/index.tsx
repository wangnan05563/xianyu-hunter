import { useEffect, useRef } from 'react'
import p5 from 'p5'
import { useTheme } from '../../contexts/ThemeContext'

/**
 * Tidal Foragers 生成艺术背景（方案 A「涌现之舞」）
 *
 * 设计来源：docs/archive/tidal-foragers-philosophy.md
 * 核心要素：群体智能涌现 + 分层流场 + 觅食节奏 + 光影层次
 *
 * 优化点（相对基础版）：
 * 1. 鱼身 3 段式（头/身/尾），尾部用正弦曲线摆动，摆幅与速度耦合
 * 2. Boids 第四规则"边缘意识"，防止鱼群被甩出屏幕
 * 3. 双层 Perlin 流场（基础洋流 + 局部涡旋），模拟湍流结构
 * 4. 双层鳞片反光：基础色 + 速度调制的银色高光斑
 * 5. 鱼群密度"潮汐呼吸"（30s 周期动态变化）
 * 6. 自适应降级：FPS 监测 + 设备分级（移动端/桌面端）
 */

interface Nutrient {
  pos: p5.Vector
  life: number
  maxLife: number
  size: number
  update(): void
  show(): void
}

interface Fish {
  pos: p5.Vector
  vel: p5.Vector
  acc: p5.Vector
  phase: number
  sizeScale: number
  followFlow(t: number, flowScale: number, flowStrength: number, flowTimeStep: number): void
  flock(neighbors: Fish[], params: BoidsParams): void
  seekNutrients(nutrients: Nutrient[], params: BoidsParams): void
  applyEdgeAwareness(canvasW: number, canvasH: number): void
  update(maxSpeed: number): void
  edges(p: p5): void
  show(colors: Palette, params: RenderParams): void
}

interface BoidsParams {
  sepRadius: number
  alignRadius: number
  cohesionRadius: number
  sepForce: number
  alignForce: number
  cohesionForce: number
  edgeForce: number
  maxSpeed: number
  maxForce: number
  nutrientRadius: number
  nutrientForce: number
}

interface Palette {
  deepSea: [number, number, number]
  shallowSea: [number, number, number]
  fishGlow: [number, number, number]
  fishSilver: [number, number, number]
  lightBeam: [number, number, number]
  trailAlpha: number
  noiseColor: [number, number, number]
  noiseAlpha: number
}

interface RenderParams {
  // 是否启用高细节渲染（5 段贝塞尔 + 双层鳞片），低端设备关闭
  highDetail: boolean
  // 拖尾透明度（越小拖尾越长）
  trailAlpha: number
  // 鱼基础尺寸缩放
  baseSize: number
}

/**
 * 设备分级：根据 navigator.hardwareConcurrency 和屏幕尺寸判断
 * 低端：核心数 <= 4 或 屏幕宽度 < 768
 * 中端：核心数 <= 8
 * 高端：其他
 */
// S4323：抽取 type alias 替代内联联合类型
type DeviceTier = 'low' | 'mid' | 'high'
function detectDeviceTier(): DeviceTier {
  // S7764：用 globalThis.window 替代 window
  // S7741：globalThis 总是已声明，直接比较即可
  if (globalThis.window === undefined) return 'mid'
  const cores = navigator.hardwareConcurrency || 4
  const smallScreen = window.innerWidth < 768
  // WebView2/嵌入式浏览器通常 hardwareConcurrency 较小，降级到低端
  if (smallScreen || cores <= 4) return 'low'
  if (cores <= 8) return 'mid'
  return 'high'
}

// ===== 工具：3 段式鱼身渲染 =====
//
// 鱼身结构：
//   头（三角）— 身（椭圆）— 尾（贝塞尔曲线）
//
// 尾部由 3 个控制点组成：尾根、尾中、尾尖
// 摆动通过 phase 偏移实现，摆幅与速度耦合
// 鱼身绘制所需的运动状态：合并 headingAngle/speed/phase 三参数降低函数签名复杂度（S107）
interface FishMotion {
  headingAngle: number
  speed: number
  phase: number
}

function drawFishBody(
  p: p5,
  pos: p5.Vector,
  motion: FishMotion,
  colors: Palette,
  params: RenderParams,
  sizeScale: number,
) {
  const { headingAngle, speed, phase } = motion
  const baseSize = params.baseSize * sizeScale
  // 速度越快身体越修长（最大拉伸 1.3 倍）
  const stretch = p.map(speed, 0, 3, 1, 1.3)
  const fishLen = baseSize * 8 * stretch
  const fishHeight = baseSize * 2.5

  p.push()
  p.translate(pos.x, pos.y)
  p.rotate(headingAngle)

  // 摆动幅度：速度越快摆得越狠（与游动真实感一致）
  const wagAmp = p.map(speed, 0, 3, 0, baseSize * 1.2)

  // ----- 尾鳍（3 个控制点 + 二次贝塞尔曲线） -----
  // 尾根 → 尾中（受 phase 摆动） → 尾尖（受 phase 偏移摆动）
  const tailRoot = { x: -fishLen * 0.3, y: 0 }
  const tailMid = { x: -fishLen * 0.6, y: p.sin(phase) * wagAmp * 0.6 }
  // S7748：去除零分数 1.0 → 1
  const tailTip = { x: -fishLen, y: p.sin(phase + 1) * wagAmp }

  // 外层辉光（仅高速时显现）
  if (speed > 0.5) {
    p.noStroke()
    p.fill(colors.fishGlow[0], colors.fishGlow[1], colors.fishGlow[2], 25)
    p.ellipse(0, 0, fishLen * 1.4, fishHeight * 2.2)
  }

  // 尾鳍填充：深色（#B85800 暗调橙色），速度低时降低不透明度
  // 用三角形构造尾鳍并叠加中间控制点，摆动由 phase 偏移实现
  // 为什么不使用 bezierVertex：p5 types 的 bezierVertex 重载只到 5 参数，
  // 直接用 vertex 画三角 + 中点偏移更稳健且效果一致
  const tailAlpha = p.map(speed, 0, 3, 150, 220)
  p.fill(184, 88, 0, tailAlpha)
  p.noStroke()
  p.beginShape()
  p.vertex(tailRoot.x, tailRoot.y - fishHeight * 0.4)
  p.vertex(tailMid.x, tailMid.y)
  p.vertex(tailTip.x, tailTip.y)
  p.vertex(tailMid.x, tailMid.y)
  p.vertex(tailRoot.x, tailRoot.y + fishHeight * 0.4)
  p.endShape(p.CLOSE)

  // ----- 鱼身（椭圆渐变） -----
  // 用两层椭圆叠加：底层暗色（腹部阴影）+ 上层品牌橙（背部）
  // 速度调制：高速时透明度增加（运动模糊感）
  const bodyAlpha = p.map(speed, 0, 3, 180, 240)
  // 腹部阴影
  p.fill(184, 88, 0, bodyAlpha * 0.7)
  p.ellipse(0, 0, fishLen * 0.7, fishHeight)
  // 背部分（品牌橙 #FF6200）
  p.fill(255, 98, 0, bodyAlpha)
  p.ellipse(0, -fishHeight * 0.15, fishLen * 0.65, fishHeight * 0.7)

  // ----- 鱼头（三角） -----
  p.fill(255, 122, 24, bodyAlpha)
  p.triangle(
    fishLen * 0.4, 0,           // 吻端
    fishLen * 0.05, -fishHeight * 0.5,  // 头上
    fishLen * 0.05, fishHeight * 0.5,   // 头下
  )

  // ----- 鳞片高光（双层） -----
  // 第一层：常驻的基础高光（小椭圆，靠近头部）
  p.fill(255, 220, 180, 100)
  p.ellipse(fishLen * 0.15, -fishHeight * 0.2, fishHeight * 0.4, fishHeight * 0.2)

  // 第二层：动态高光斑（仅高速时显现，模拟鳞片闪烁）
  if (speed > 1.2 && params.highDetail) {
    const shimmer = (p.sin(phase * 1.5) + 1) * 0.5
    if (shimmer > 0.6) {
      p.fill(colors.fishSilver[0], colors.fishSilver[1], colors.fishSilver[2], 180 * shimmer)
      p.ellipse(0, 0, fishLen * 0.3, fishHeight * 0.3)
    }
  }

  p.pop()
}

// ===== 鱼工厂函数 =====
function createFish(
  p: p5,
  x: number,
  y: number,
  maxSpeed: number,
): Fish {
  const pos = p.createVector(x, y)
  const angle = p.random(p.TWO_PI)
  const vel = p5.Vector.fromAngle(angle).mult(p.random(0.5, maxSpeed * 0.8))
  const acc = p.createVector(0, 0)
  let phase = p.random(p.TWO_PI)
  // sizeScale 让不同鱼大小略有差异，增加群落层次感
  const sizeScale = p.random(0.7, 1.3)

  const fish: Fish = {
    pos,
    vel,
    acc,
    sizeScale,
    get phase() { return phase },
    // 流场跟随：双层 Perlin 噪声
    // - 第一层（基础洋流）：大尺度缓慢变化
    // - 第二层（局部涡旋）：小尺度快速变化，叠加产生湍流
    followFlow(t: number, flowScale: number, flowStrength: number, flowTimeStep: number) {
      // 基础洋流
      const baseAngle = p.noise(
        pos.x * flowScale,
        pos.y * flowScale,
        t * flowTimeStep,
      ) * p.TWO_PI * 2
      const baseFlow = p5.Vector.fromAngle(baseAngle).mult(flowStrength)

      // 局部涡旋（更高频，振幅更小）
      const eddyAngle = p.noise(
        pos.x * flowScale * 3 + 100,
        pos.y * flowScale * 3 + 100,
        t * flowTimeStep * 2,
      ) * p.TWO_PI * 2
      const eddyFlow = p5.Vector.fromAngle(eddyAngle).mult(flowStrength * 0.4)

      acc.add(baseFlow).add(eddyFlow)
    },
    // 群体规则：分离 + 对齐 + 聚集
    flock(neighbors: Fish[], params: BoidsParams) {
      const sep = p.createVector(0, 0)
      const ali = p.createVector(0, 0)
      const coh = p.createVector(0, 0)
      let sepCount = 0, aliCount = 0, cohCount = 0

      for (const other of neighbors) {
        if (other === fish) continue
        const d = p5.Vector.dist(pos, other.pos)
        if (d > 0 && d < params.sepRadius) {
          const diff = p5.Vector.sub(pos, other.pos).normalize().div(d)
          sep.add(diff)
          sepCount++
        }
        if (d > 0 && d < params.alignRadius) {
          ali.add(other.vel)
          aliCount++
        }
        if (d > 0 && d < params.cohesionRadius) {
          coh.add(other.pos)
          cohCount++
        }
      }

      if (sepCount > 0) {
        sep.div(sepCount).setMag(params.maxSpeed).sub(vel).limit(params.maxForce).mult(params.sepForce)
        acc.add(sep)
      }
      if (aliCount > 0) {
        ali.div(aliCount).setMag(params.maxSpeed).sub(vel).limit(params.maxForce).mult(params.alignForce)
        acc.add(ali)
      }
      if (cohCount > 0) {
        coh.div(cohCount).sub(pos).setMag(params.maxSpeed).sub(vel).limit(params.maxForce).mult(params.cohesionForce)
        acc.add(coh)
      }
    },
    // 觅食：被光点吸引
    seekNutrients(nutrients: Nutrient[], params: BoidsParams) {
      for (const n of nutrients) {
        const d = p5.Vector.dist(pos, n.pos)
        if (d < params.nutrientRadius && d > 0) {
          // 距离越近吸引力越强（线性衰减）
          const force = p5.Vector.sub(n.pos, pos).normalize()
            .mult(params.nutrientForce * (1 - d / params.nutrientRadius))
          acc.add(force)
        }
      }
    },
    // 第四规则"边缘意识"：距屏幕边缘 < 80px 时产生向心力
    // 防止鱼群被甩出屏幕导致视觉断裂
    applyEdgeAwareness(canvasW: number, canvasH: number) {
      const margin = 80
      const edgeForce = 0.05
      if (pos.x < margin) acc.x += edgeForce * (margin - pos.x) / margin
      if (pos.x > canvasW - margin) acc.x -= edgeForce * (pos.x - (canvasW - margin)) / margin
      if (pos.y < margin) acc.y += edgeForce * (margin - pos.y) / margin
      if (pos.y > canvasH - margin) acc.y -= edgeForce * (pos.y - (canvasH - margin)) / margin
    },
    update(maxSpeed: number) {
      vel.add(acc).limit(maxSpeed)
      pos.add(vel)
      acc.mult(0)
      phase += 0.1
    },
    // 环绕边界（让鱼群从一侧穿到另一侧）
    edges(p: p5) {
      if (pos.x < -20) pos.x = p.width + 20
      if (pos.x > p.width + 20) pos.x = -20
      if (pos.y < -20) pos.y = p.height + 20
      if (pos.y > p.height + 20) pos.y = -20
    },
    show(colors: Palette, params: RenderParams) {
      const headingAngle = vel.heading()
      const speed = vel.mag()
      drawFishBody(p, pos, { headingAngle, speed, phase }, colors, params, sizeScale)
    },
  }
  return fish
}

function createNutrient(p: p5): Nutrient {
  let pos = p.createVector(p.random(p.width), p.random(p.height))
  let maxLife = p.random(300, 600)
  let life = maxLife
  let size = p.random(3, 6)

  return {
    get pos() { return pos },
    get life() { return life },
    get maxLife() { return maxLife },
    get size() { return size },
    update() {
      life--
      if (life <= 0) {
        pos = p.createVector(p.random(p.width), p.random(p.height))
        maxLife = p.random(300, 600)
        life = maxLife
        size = p.random(3, 6)
      }
    },
    show() {
      const alpha = p.map(life, 0, maxLife, 0, 255)
      const pulse = (p.sin(p.frameCount * 0.05) + 1) * 0.5
      const showSize = size + pulse * 2

      p.noStroke()
      // 外层光晕（金色 #FFD700），4 层叠加
      for (let i = 4; i > 0; i--) {
        p.fill(255, 215, 0, alpha * 0.1 / i)
        p.ellipse(pos.x, pos.y, showSize * i * 2)
      }
      // 核心
      p.fill(255, 255, 220, alpha)
      p.ellipse(pos.x, pos.y, showSize)
    },
  }
}

export default function TidalForagers() {
  const containerRef = useRef<HTMLDivElement>(null)
  const instanceRef = useRef<p5 | null>(null)
  const { isDark } = useTheme()

  useEffect(() => {
    // S4325：用本地变量替代 containerRef.current! 断言
    const container = containerRef.current
    if (!container) return

    const sketch = (p: p5) => {
      // ===== 设备分级（决定鱼群上限与是否启用高细节） =====
      // 显式标注字面量联合类型，避免 TS 收窄后丢失 'low' 可能性
      const tier: DeviceTier = detectDeviceTier()
      // S3358：嵌套三元拆分为 if/else
      // 鱼群数量上限：低端 80，中端 180，高端 280
      let FISH_LIMIT = 280
      if (tier === 'low') FISH_LIMIT = 80
      else if (tier === 'mid') FISH_LIMIT = 180
      const highDetail = tier !== 'low'

      // ===== Boids 参数 =====
      const boidsParams: BoidsParams = {
        sepRadius: 24,
        alignRadius: 48,
        cohesionRadius: 56,
        sepForce: 1.8,
        // S7748：去除零分数 1.0 → 1
        alignForce: 1,
        cohesionForce: 0.8,
        edgeForce: 0.05,
        maxSpeed: 2.4,
        maxForce: 0.06,
        nutrientRadius: 180,
        nutrientForce: 0.4,
      }

      // ===== 流场参数 =====
      const flowScale = 0.0025
      const flowStrength = 0.32
      const flowTimeStep = 0.0008

      // ===== 渲染参数 =====
      const renderParams: RenderParams = {
        highDetail,
        trailAlpha: 22,
        // S7748：去除零分数 1.0 → 1
        baseSize: 1,
      }

      // ===== 颜色调色板 =====
      const darkPalette: Palette = {
        deepSea: [10, 25, 45],
        shallowSea: [26, 47, 74],
        fishGlow: [255, 180, 100],
        fishSilver: [230, 241, 255],
        lightBeam: [180, 220, 255],
        trailAlpha: 22,
        noiseColor: [255, 255, 255],
        noiseAlpha: 8,
      }
      const lightPalette: Palette = {
        deepSea: [216, 240, 247],
        shallowSea: [127, 200, 232],
        fishGlow: [255, 200, 130],
        fishSilver: [255, 255, 255],
        lightBeam: [255, 255, 255],
        trailAlpha: 18,
        noiseColor: [40, 80, 120],
        noiseAlpha: 12,
      }
      const COLORS: Palette = isDark ? darkPalette : lightPalette

      // ===== 全局状态 =====
      let fishes: Fish[] = []
      let nutrients: Nutrient[] = []
      let bgGraphics: p5.Graphics
      let time = 0

      // ===== 空间分区网格 =====
      const gridSize = 70
      const grid: Map<string, Fish[]> = new Map()

      function buildGrid() {
        grid.clear()
        for (const fish of fishes) {
          const cx = Math.floor(fish.pos.x / gridSize)
          const cy = Math.floor(fish.pos.y / gridSize)
          const key = `${cx},${cy}`
          if (!grid.has(key)) grid.set(key, [])
          grid.get(key)!.push(fish)
        }
      }

      function getNeighbors(fish: Fish): Fish[] {
        const cx = Math.floor(fish.pos.x / gridSize)
        const cy = Math.floor(fish.pos.y / gridSize)
        const neighbors: Fish[] = []
        for (let dx = -1; dx <= 1; dx++) {
          for (let dy = -1; dy <= 1; dy++) {
            const key = `${cx + dx},${cy + dy}`
            const cell = grid.get(key)
            if (cell) neighbors.push(...cell)
          }
        }
        return neighbors
      }

      // ===== 预渲染背景 =====
      function createBackground() {
        bgGraphics = p.createGraphics(p.width, p.height)
        for (let y = 0; y < p.height; y++) {
          const t = y / p.height
          const r = p.lerp(COLORS.deepSea[0], COLORS.shallowSea[0], t)
          const g = p.lerp(COLORS.deepSea[1], COLORS.shallowSea[1], t)
          const b = p.lerp(COLORS.deepSea[2], COLORS.shallowSea[2], t)
          bgGraphics.stroke(r, g, b)
          bgGraphics.line(0, y, p.width, y)
        }
        bgGraphics.noStroke()
        for (let i = 0; i < 200; i++) {
          const x = p.random(p.width)
          const y = p.random(p.height)
          bgGraphics.fill(
            COLORS.noiseColor[0],
            COLORS.noiseColor[1],
            COLORS.noiseColor[2],
            p.random(COLORS.noiseAlpha * 0.3, COLORS.noiseAlpha),
          )
          bgGraphics.ellipse(x, y, p.random(1, 2))
        }
      }

      // ===== 光柱（水面折射） =====
      function drawLightBeams() {
        p.push()
        p.blendMode(p.ADD)
        p.noStroke()
        const beamCount = 3
        for (let i = 0; i < beamCount; i++) {
          const x = (p.width / (beamCount + 1)) * (i + 1)
            + p.sin(time * 0.0003 + i * 2) * 80
          const beamWidth = 120 + p.sin(time * 0.001 + i) * 30
          for (let j = 0; j < 8; j++) {
            const alpha = 8 - j
            p.fill(COLORS.lightBeam[0], COLORS.lightBeam[1], COLORS.lightBeam[2], alpha)
            p.ellipse(x, j * p.height / 8, beamWidth - j * 5, 40)
          }
        }
        p.blendMode(p.BLEND)
        p.pop()
      }

      // ===== 鱼群密度呼吸（30s 周期） =====
      // 呼吸函数：sin 曲线，范围 [0.5, 1.0]
      function targetFishCount(t: number): number {
        const breathCycle = 1800 // 30s * 60fps
        const phase = (t % breathCycle) / breathCycle
        const breathFactor = 0.5 + 0.5 * Math.sin(phase * Math.PI * 2)
        return Math.floor(FISH_LIMIT * (0.5 + breathFactor * 0.5))
      }

      function adjustFishPopulation(target: number) {
        if (fishes.length < target) {
          while (fishes.length < target) {
            fishes.push(createFish(p, p.random(p.width), p.random(p.height), boidsParams.maxSpeed))
          }
        } else if (fishes.length > target) {
          fishes = fishes.slice(0, target)
        }
      }

      // ===== FPS 监测 + 自适应降级 =====
      // 每 60 帧采样一次 FPS，连续 3 次低于 45 触发降级
      let fpsSampleFrames = 0
      let lastFpsCheckTime = p.millis()
      let lowFpsCount = 0
      // 显式标注为字面量联合类型，避免 TS 收窄导致后续比较死代码告警
      let currentTier: 'low' | 'mid' | 'high' = tier

      function checkFpsAndAdapt() {
        fpsSampleFrames++
        if (fpsSampleFrames < 60) return
        const elapsed = p.millis() - lastFpsCheckTime
        const fps = (fpsSampleFrames / elapsed) * 1000
        fpsSampleFrames = 0
        lastFpsCheckTime = p.millis()

        if (fps < 45 && currentTier !== 'low') {
          lowFpsCount++
          if (lowFpsCount >= 3) {
            // 降级到低质量
            currentTier = 'low'
            renderParams.highDetail = false
            // 立即减少鱼数
            adjustFishPopulation(Math.min(fishes.length, 80))
          }
        } else if (fps > 55 && currentTier === 'low' && highDetail) {
          // 恢复（仅当设备原生支持更高品质）
          currentTier = tier
          renderParams.highDetail = highDetail
          lowFpsCount = 0
        } else {
          lowFpsCount = 0
        }
      }

      // ===== p5 生命周期 =====
      p.setup = () => {
        const canvas = p.createCanvas(window.innerWidth, window.innerHeight)
        // S4325：用闭包内本地变量 container 替代 containerRef.current!
        canvas.parent(container)
        createBackground()
        fishes = []
        const initialCount = targetFishCount(0)
        for (let i = 0; i < initialCount; i++) {
          fishes.push(createFish(p, p.random(p.width), p.random(p.height), boidsParams.maxSpeed))
        }
        nutrients = []
        for (let i = 0; i < 6; i++) {
          nutrients.push(createNutrient(p))
        }
      }

      p.draw = () => {
        time++

        // 拖尾层
        p.image(bgGraphics, 0, 0)
        p.noStroke()
        const trailColor = isDark ? COLORS.deepSea : COLORS.shallowSea
        p.fill(trailColor[0], trailColor[1], trailColor[2], COLORS.trailAlpha)
        p.rect(0, 0, p.width, p.height)

        // 光柱
        drawLightBeams()

        // 空间分区
        buildGrid()

        // 光点
        for (const n of nutrients) {
          n.update()
          n.show()
        }

        // 鱼群：根据呼吸曲线调整数量
        const target = targetFishCount(time)
        adjustFishPopulation(target)

        // 更新 + 绘制鱼
        for (const fish of fishes) {
          fish.followFlow(time, flowScale, flowStrength, flowTimeStep)
          const neighbors = getNeighbors(fish)
          fish.flock(neighbors, boidsParams)
          fish.seekNutrients(nutrients, boidsParams)
          fish.applyEdgeAwareness(p.width, p.height)
          fish.update(boidsParams.maxSpeed)
          fish.edges(p)
          fish.show(COLORS, renderParams)
        }

        // FPS 监测（每 60 帧一次，低开销）
        checkFpsAndAdapt()
      }

      p.windowResized = () => {
        p.resizeCanvas(globalThis.innerWidth, globalThis.innerHeight)
        createBackground()
        const target = targetFishCount(time)
        adjustFishPopulation(target)
      }
    }

    instanceRef.current = new p5(sketch, container)

    return () => {
      instanceRef.current?.remove()
      instanceRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isDark])

  return (
    <div
      ref={containerRef}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 0,
        pointerEvents: 'none',
      }}
      aria-hidden="true"
    />
  )
}
