// @vitest-environment node
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// T02654：「闲鱼内容关联」面板的任务下拉曾经直接复用列表的当页数据，
// 任务多于 pageSize 时，分页范围外的任务在下拉里选不到，其关联也就无从删除。
// 这里锁住三件事：候选来自独立端点、候选变量确实被下拉消费、候选随列表变化刷新。

const src = (rel: string) => readFileSync(resolve(__dirname, '../../..', rel), 'utf-8')

const list = src('pages/Tasks/TaskList.tsx')
const taskApiSrc = src('api/task.ts')

describe('关联面板任务下拉与列表分页解耦（T02654）', () => {
  it('下拉候选用 linkTaskOptions，不再复用当页 tasks', () => {
    expect(list).toContain('const [linkTaskOptions, setLinkTaskOptions] = useState<TaskOption[]>([])')
    expect(list).toContain('options={linkTaskOptions.map(')
    expect(list).not.toContain('options={tasks.map(')
  })

  it('候选走独立的轻量端点，而不是把 list 的 limit 调大', () => {
    expect(list).toContain('taskApi.options()')
    expect(taskApiSrc).toContain("client.get<{ items: TaskOption[]; count: number }>('/api/tasks/options')")
  })

  it('拉到的候选必须落到 linkTaskOptions 本身（接错对象等于没修）', () => {
    const block = list.match(/const refreshLinkTaskOptions = useCallback\([\s\S]*?\}, \[\]\)/)?.[0] ?? ''
    expect(block).toContain('taskApi.options()')
    expect(block).toContain('setLinkTaskOptions(res.items || [])')
  })

  it('面板打开时拉候选，并在任务列表变化后跟着刷新', () => {
    const effect = list.match(/useEffect\(\(\) => \{\s*\n\s*if \(linkPanelOpen\) refreshLinkTaskOptions\(\)\s*\n\s*\}, \[[^\]]*\]\)/)?.[0] ?? ''
    expect(effect).toContain('if (linkPanelOpen) refreshLinkTaskOptions()')
    expect(effect).toContain('tasks]')
  })
})
