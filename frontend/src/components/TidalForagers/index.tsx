import { useEffect, useRef } from 'react'
import p5 from 'p5'
import { useTheme } from '../../contexts/ThemeContext'

/**
 * Tidal Foragers 生成艺术背景
 *
 * 基于 Boids 群体智能算法 + Perlin 噪声流场，
 * 模拟闲鱼猎人"在流动中寻找价值"的主题。
 * 鱼群在深海中顺流游动，被光点（养分/机会）吸引，
 * 形成动态的觅食舞蹈。
 *
 * 主题适配：
 * - 暗色模式：深海蓝渐变（#0a1929 → #1a2f4a），暗调神秘
 * - 亮色模式：浅海蓝渐变（#d8f0f7 → #7fc8e8），明亮清新
 */
export default function TidalForagers() {
  const containerRef = useRef<HTMLDivElement>(null)
  const instanceRef = useRef<p5 | null>(null)
  const { isDark } = useTheme()

  useEffect(() => {
    if (!containerRef.current) return

    const sketch = (p: p5) => {
      // ===== 参数配置 =====
      const PARAMS = {
        fishCount: 220,          // 鱼群数量（根据屏幕大小动态调整）
        flowScale: 0.0025,       // 流场噪声尺度（越小越平滑）
        flowStrength: 0.35,      // 流场对鱼群的影响力度
        flowTimeStep: 0.0008,    // 流场时间演化速度
        sepRadius: 28,           // 分离半径
        alignRadius: 50,         // 对齐半径
        cohesionRadius: 60,      // 聚集半径
        sepForce: 1.8,           // 分离力度
        alignForce: 1.0,         // 对齐力度
        cohesionForce: 0.8,      // 聚集力度
        maxSpeed: 2.6,            // 最大速度
        maxForce: 0.06,           // 最大转向力
        nutrientCount: 6,        // 光点数量
        nutrientRadius: 180,     // 光点吸引半径
        nutrientForce: 0.4,      // 光点吸引力
        trailAlpha: 22,          // 拖尾透明度（越小拖尾越长）
      }

      // ===== 颜色调色板 =====
      // 根据主题切换调色板：暗色深海 vs 亮色浅海
      // 设计原则：保持鱼群橙色（#FF6200）和光点金色不变，背景色适应主题
      const darkPalette = {
        // 深海：神秘深邃
        deepSea: [10, 25, 45] as [number, number, number],       // #0a1929
        shallowSea: [26, 47, 74] as [number, number, number],    // #1a2f4a
        fishGlow: [255, 180, 100] as [number, number, number],   // 橙色辉光
        fishSilver: [230, 241, 255] as [number, number, number], // 银白高光
        lightBeam: [180, 220, 255] as [number, number, number],  // 冷蓝光柱
        trailAlpha: 22,
        // 海水噪点（亮色主题下用深蓝小点，模拟海水颗粒）
        noiseColor: [255, 255, 255] as [number, number, number],
        noiseAlpha: 8,
      }
      const lightPalette = {
        // 浅海：明亮清新
        deepSea: [216, 240, 247] as [number, number, number],    // #d8f0f7
        shallowSea: [127, 200, 232] as [number, number, number], // #7fc8e8
        fishGlow: [255, 200, 130] as [number, number, number],   // 略亮橙
        fishSilver: [255, 255, 255] as [number, number, number], // 纯白高光
        lightBeam: [255, 255, 255] as [number, number, number],  // 暖白光柱
        trailAlpha: 18,                                            // 拖尾稍短
        noiseColor: [40, 80, 120] as [number, number, number],   // 深蓝小点
        noiseAlpha: 12,
      }
      const COLORS = isDark ? darkPalette : lightPalette

      // ===== 鱼类（Boids 单元）=====
      class Fish {
        pos: p5.Vector
        vel: p5.Vector
        acc: p5.Vector
        phase: number  // 用于鳞片闪烁

        constructor(x: number, y: number) {
          this.pos = p.createVector(x, y)
          const angle = p.random(p.TWO_PI)
          this.vel = p5.Vector.fromAngle(angle).mult(p.random(1, PARAMS.maxSpeed))
          this.acc = p.createVector(0, 0)
          this.phase = p.random(p.TWO_PI)
        }

        // 跟随 Perlin 噪声流场
        followFlow(t: number) {
          const angle = p.noise(
            this.pos.x * PARAMS.flowScale,
            this.pos.y * PARAMS.flowScale,
            t * PARAMS.flowTimeStep,
          ) * p.TWO_PI * 2
          const flow = p5.Vector.fromAngle(angle).mult(PARAMS.flowStrength)
          this.acc.add(flow)
        }

        // Boids 三规则：分离、对齐、聚集
        flock(neighbors: Fish[]) {
          const sep = p.createVector(0, 0)
          const ali = p.createVector(0, 0)
          const coh = p.createVector(0, 0)
          let sepCount = 0, aliCount = 0, cohCount = 0

          for (const other of neighbors) {
            if (other === this) continue
            const d = p5.Vector.dist(this.pos, other.pos)
            if (d > 0 && d < PARAMS.sepRadius) {
              const diff = p5.Vector.sub(this.pos, other.pos).normalize().div(d)
              sep.add(diff)
              sepCount++
            }
            if (d > 0 && d < PARAMS.alignRadius) {
              ali.add(other.vel)
              aliCount++
            }
            if (d > 0 && d < PARAMS.cohesionRadius) {
              coh.add(other.pos)
              cohCount++
            }
          }

          if (sepCount > 0) {
            sep.div(sepCount).setMag(PARAMS.maxSpeed).sub(this.vel).limit(PARAMS.maxForce).mult(PARAMS.sepForce)
            this.acc.add(sep)
          }
          if (aliCount > 0) {
            ali.div(aliCount).setMag(PARAMS.maxSpeed).sub(this.vel).limit(PARAMS.maxForce).mult(PARAMS.alignForce)
            this.acc.add(ali)
          }
          if (cohCount > 0) {
            coh.div(cohCount).sub(this.pos).setMag(PARAMS.maxSpeed).sub(this.vel).limit(PARAMS.maxForce).mult(PARAMS.cohesionForce)
            this.acc.add(coh)
          }
        }

        // 被光点（养分）吸引
        seekNutrients(nutrients: Nutrient[]) {
          for (const n of nutrients) {
            const d = p5.Vector.dist(this.pos, n.pos)
            if (d < PARAMS.nutrientRadius && d > 0) {
              const force = p5.Vector.sub(n.pos, this.pos).normalize()
                .mult(PARAMS.nutrientForce * (1 - d / PARAMS.nutrientRadius))
              this.acc.add(force)
            }
          }
        }

        update() {
          this.vel.add(this.acc).limit(PARAMS.maxSpeed)
          this.pos.add(this.vel)
          this.acc.mult(0)
          this.phase += 0.1
        }

        // 环绕边界（让鱼群从一侧穿到另一侧）
        edges() {
          if (this.pos.x < -10) this.pos.x = p.width + 10
          if (this.pos.x > p.width + 10) this.pos.x = -10
          if (this.pos.y < -10) this.pos.y = p.height + 10
          if (this.pos.y > p.height + 10) this.pos.y = -10
        }

        // 绘制鱼（三角形 + 辉光）
        show() {
          const angle = this.vel.heading()
          const speed = this.vel.mag()
          // 速度越快越亮
          const brightness = p.map(speed, 0, PARAMS.maxSpeed, 0.4, 1)
          // 鳞片闪烁
          const shimmer = (p.sin(this.phase) + 1) * 0.5

          p.push()
          p.translate(this.pos.x, this.pos.y)
          p.rotate(angle)

          // 外层辉光
          p.noStroke()
          p.fill(COLORS.fishGlow[0], COLORS.fishGlow[1], COLORS.fishGlow[2], 30 * brightness)
          p.ellipse(0, 0, 14, 7)

          // 鱼身（品牌橙三角 #FF6200）
          const r = 255 * brightness + COLORS.fishSilver[0] * shimmer * 0.3
          const g = 98 * brightness + COLORS.fishSilver[1] * shimmer * 0.3
          const b = 0 * brightness + COLORS.fishSilver[2] * shimmer * 0.3
          p.fill(r, g, b, 220)
          p.triangle(6, 0, -4, -3, -4, 3)

          // 鳞片高光
          if (shimmer > 0.7) {
            p.fill(COLORS.fishSilver[0], COLORS.fishSilver[1], COLORS.fishSilver[2], 180 * shimmer)
            p.ellipse(0, 0, 4, 2)
          }

          p.pop()
        }
      }

      // ===== 光点（养分/机会）=====
      class Nutrient {
        pos: p5.Vector
        life: number
        maxLife: number
        size: number

        constructor() {
          this.pos = p.createVector(p.random(p.width), p.random(p.height))
          this.maxLife = p.random(300, 600)
          this.life = this.maxLife
          this.size = p.random(3, 6)
        }

        update() {
          this.life--
          if (this.life <= 0) {
            this.pos = p.createVector(p.random(p.width), p.random(p.height))
            this.maxLife = p.random(300, 600)
            this.life = this.maxLife
            this.size = p.random(3, 6)
          }
        }

        show() {
          const alpha = p.map(this.life, 0, this.maxLife, 0, 255)
          const pulse = (p.sin(p.frameCount * 0.05) + 1) * 0.5
          const size = this.size + pulse * 2

          // 外层光晕（金色 #FFD700）
          p.noStroke()
          for (let i = 4; i > 0; i--) {
            p.fill(255, 215, 0, alpha * 0.1 / i)
            p.ellipse(this.pos.x, this.pos.y, size * i * 2)
          }
          // 核心
          p.fill(255, 255, 220, alpha)
          p.ellipse(this.pos.x, this.pos.y, size)
        }
      }

      // ===== 全局状态 =====
      let fishes: Fish[] = []
      let nutrients: Nutrient[] = []
      let bgGraphics: p5.Graphics  // 预渲染背景
      let time = 0

      // ===== 空间分区网格（优化邻居查找）=====
      // 将屏幕划分为网格，只检查同一网格和相邻网格的鱼
      const gridSize = 80
      let grid: Map<string, Fish[]> = new Map()

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

      // ===== 预渲染背景渐变 =====
      function createBackground() {
        bgGraphics = p.createGraphics(p.width, p.height)
        // 垂直渐变：深海/浅海蓝
        for (let y = 0; y < p.height; y++) {
          const t = y / p.height
          const r = p.lerp(COLORS.deepSea[0], COLORS.shallowSea[0], t)
          const g = p.lerp(COLORS.deepSea[1], COLORS.shallowSea[1], t)
          const b = p.lerp(COLORS.deepSea[2], COLORS.shallowSea[2], t)
          bgGraphics.stroke(r, g, b)
          bgGraphics.line(0, y, p.width, y)
        }
        // 添加噪点纹理（模拟海水颗粒，颜色根据主题适配）
        bgGraphics.noStroke()
        for (let i = 0; i < 200; i++) {
          const x = p.random(p.width)
          const y = p.random(p.height)
          bgGraphics.fill(
            COLORS.noiseColor[0],
            COLORS.noiseColor[1],
            COLORS.noiseColor[2],
            p.random(COLORS.noiseAlpha * 0.3, COLORS.noiseAlpha)
          )
          bgGraphics.ellipse(x, y, p.random(1, 2))
        }
      }

      // ===== 绘制光柱（水面折射的阳光）=====
      function drawLightBeams() {
        p.push()
        p.blendMode(p.ADD)
        p.noStroke()
        const beamCount = 3
        for (let i = 0; i < beamCount; i++) {
          const x = (p.width / (beamCount + 1)) * (i + 1)
            + p.sin(time * 0.0003 + i * 2) * 80
          const beamWidth = 120 + p.sin(time * 0.001 + i) * 30
          // 光柱从顶部向下渐变
          for (let j = 0; j < 8; j++) {
            const alpha = 8 - j
            p.fill(COLORS.lightBeam[0], COLORS.lightBeam[1], COLORS.lightBeam[2], alpha)
            p.ellipse(x, j * p.height / 8, beamWidth - j * 5, 40)
          }
        }
        p.blendMode(p.BLEND)
        p.pop()
      }

      // ===== p5 生命周期 =====
      p.setup = () => {
        const canvas = p.createCanvas(window.innerWidth, window.innerHeight)
        canvas.parent(containerRef.current!)
        // 根据屏幕大小调整鱼群数量
        PARAMS.fishCount = Math.min(280, Math.max(120, Math.floor((p.width * p.height) / 8000)))
        createBackground()
        // 初始化鱼群
        fishes = []
        for (let i = 0; i < PARAMS.fishCount; i++) {
          fishes.push(new Fish(p.random(p.width), p.random(p.height)))
        }
        // 初始化光点
        nutrients = []
        for (let i = 0; i < PARAMS.nutrientCount; i++) {
          nutrients.push(new Nutrient())
        }
      }

      p.draw = () => {
        time++

        // 拖尾效果：覆盖半透明背景（拖尾用底层深色，保留渐变感）
        p.image(bgGraphics, 0, 0)
        // 拖尾层（用浅海色做底，亮色主题下用更亮的蓝）
        p.noStroke()
        const trailColor = isDark
          ? [COLORS.deepSea[0], COLORS.deepSea[1], COLORS.deepSea[2]]
          : [COLORS.shallowSea[0], COLORS.shallowSea[1], COLORS.shallowSea[2]]
        p.fill(trailColor[0], trailColor[1], trailColor[2], COLORS.trailAlpha)
        p.rect(0, 0, p.width, p.height)

        // 光柱
        drawLightBeams()

        // 构建空间分区网格
        buildGrid()

        // 更新和绘制光点
        for (const n of nutrients) {
          n.update()
          n.show()
        }

        // 更新和绘制鱼群
        for (const fish of fishes) {
          fish.followFlow(time)
          const neighbors = getNeighbors(fish)
          fish.flock(neighbors)
          fish.seekNutrients(nutrients)
          fish.update()
          fish.edges()
          fish.show()
        }
      }

      p.windowResized = () => {
        p.resizeCanvas(window.innerWidth, window.innerHeight)
        createBackground()
        // 重新调整鱼群数量
        PARAMS.fishCount = Math.min(280, Math.max(120, Math.floor((p.width * p.height) / 8000)))
        // 如果鱼群数量不够，补充
        while (fishes.length < PARAMS.fishCount) {
          fishes.push(new Fish(p.random(p.width), p.random(p.height)))
        }
        // 如果鱼群数量过多，裁剪
        if (fishes.length > PARAMS.fishCount) {
          fishes = fishes.slice(0, PARAMS.fishCount)
        }
      }
    }

    instanceRef.current = new p5(sketch, containerRef.current!)

    return () => {
      instanceRef.current?.remove()
      instanceRef.current = null
    }
    // 依赖 isDark：主题切换时销毁并重建 p5 实例
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
