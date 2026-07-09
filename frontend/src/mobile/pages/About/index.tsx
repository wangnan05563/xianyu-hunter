// frontend/src/mobile/pages/About/index.tsx
// 移动端关于：系统信息 + 版本检查更新
// 设计要点：极简页，仅展示 aboutApi.get() 返回的系统元信息 + 检查更新按钮
import { useEffect, useState, useCallback } from 'react'
import {
  Card, Spin, App, Button, Descriptions, Tag, Space, theme, Alert,
} from 'antd'
import { ReloadOutlined, CheckCircleOutlined, InfoCircleOutlined } from '@ant-design/icons'
import { aboutApi } from '../../../api'
import type { AboutInfo, UpdateCheckResult } from '../../../api/about'
import { extractApiError } from '../../../utils/apiError'

export default function MobileAbout() {
  const { message } = App.useApp()
  const { token: themeToken } = theme.useToken()
  const [info, setInfo] = useState<AboutInfo | null>(null)
  const [update, setUpdate] = useState<UpdateCheckResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [checking, setChecking] = useState(false)

  const load = useCallback(async (): Promise<void> => {
    setLoading(true)
    try {
      const data = await aboutApi.get()
      setInfo(data)
    } catch (e) {
      message.error(extractApiError(e, '加载失败'), 3)
    } finally {
      setLoading(false)
    }
  }, [message])

  useEffect(() => { void load() }, [load])

  const checkUpdate = async (): Promise<void> => {
    setChecking(true)
    try {
      const result = await aboutApi.checkUpdate()
      setUpdate(result)
      if (result.has_update) {
        message.info(`发现新版本 ${result.latest}`)
      } else {
        message.success('已是最新版本')
      }
    } catch (e) {
      message.error(extractApiError(e, '检查更新失败'), 3)
    } finally {
      setChecking(false)
    }
  }

  if (loading || !info) {
    return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>
  }

  return (
    <div>
      {/* 产品信息 */}
      <Card size="small" style={{ marginBottom: 12 }}>
        <div style={{ textAlign: 'center', marginBottom: 16 }}>
          <InfoCircleOutlined style={{ fontSize: 48, color: '#E20613' }} />
          <div style={{ fontSize: 20, fontWeight: 600, marginTop: 8 }}>{info.product}</div>
          <Tag color="red" style={{ marginTop: 4 }}>v{info.version}</Tag>
        </div>
        <Descriptions column={1} size="small">
          <Descriptions.Item label="版本">{info.version}</Descriptions.Item>
          <Descriptions.Item label="构建日期">{info.build_date}</Descriptions.Item>
          <Descriptions.Item label="Git">
            <code style={{ fontSize: 11 }}>{info.git_sha.slice(0, 8)}</code>
          </Descriptions.Item>
          <Descriptions.Item label="Python">{info.python}</Descriptions.Item>
          <Descriptions.Item label="平台">{info.platform}</Descriptions.Item>
        </Descriptions>
      </Card>

      {/* 更新检查 */}
      <Card size="small" style={{ marginBottom: 12 }} title="检查更新">
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          <Button
            type="primary"
            block
            icon={<CheckCircleOutlined />}
            loading={checking}
            onClick={checkUpdate}
          >
            检查更新
          </Button>
          {update && (
            <>
              {update.has_update ? (
                <Alert
                  type="success"
                  showIcon
                  message={`发现新版本 v${update.latest}`}
                  description={
                    <div>
                      <div>当前：v{update.current}</div>
                      {update.published_at && (
                        <div style={{ fontSize: 11 }}>
                          发布于 {new Date(update.published_at).toLocaleDateString('zh-CN')}
                        </div>
                      )}
                      <Button
                        type="link"
                        href={update.release_url}
                        target="_blank"
                        style={{ padding: 0, fontSize: 12 }}
                      >
                        查看发布详情 →
                      </Button>
                    </div>
                  }
                />
              ) : (
                <Alert type="success" showIcon message="已是最新版本" />
              )}
              {update.source === 'local' && (
                <div style={{ fontSize: 11, color: themeToken.colorTextTertiary }}>
                  ※ 本地缓存数据，可能是离线降级
                </div>
              )}
            </>
          )}
        </Space>
      </Card>

      <div style={{ textAlign: 'center', fontSize: 11, color: themeToken.colorTextTertiary }}>
        <Button type="text" size="small" icon={<ReloadOutlined />} onClick={() => void load()}>
          刷新信息
        </Button>
      </div>
    </div>
  )
}
