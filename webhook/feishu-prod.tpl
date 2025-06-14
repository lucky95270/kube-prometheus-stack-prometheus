{{ $alertmanagerURL := "http://192.168.233.32:32093" -}}
{{ $alerts := .alerts -}}
{{ $grafanaURL := "http://192.168.233.32:32030/d/HmKjz4pHk/kubernetesji-qun-jian-kong-mian-ban?orgId=1&refresh=5s" -}}
{{ range $alert := $alerts -}}
  {{ $groupKey := printf "%s|%s" $alert.labels.alertname $alert.status -}}
  {{ $urimsg := "" -}}
  {{ range $key,$value := $alert.labels -}}
    {{ $urimsg = print $urimsg $key "%3D%22" $value "%22%2C" -}}
  {{ end -}}
  {{ if eq $alert.status "resolved" -}}
🟢 Kubernetes 集群恢复通知 🟢
  {{ else -}}
🚨 Kubernetes 集群告警通知 🚨
  {{ end -}}
---
🔔 **告警名称**: {{ $alert.labels.alertname }}
🚩 **告警级别**: {{ $alert.labels.severity }}
{{ if eq $alert.status "resolved" }}✅ **告警状态**: {{ $alert.status }}{{ else }}🔥 **告警状态**: {{ $alert.status }}{{ end }}
🕒 **开始时间**: {{ GetCSTtime $alert.startsAt }}
{{ if eq $alert.status "resolved" }}🕒 **结束时间**: {{ GetCSTtime $alert.endsAt }}{{ end }}
---
📌 **告警详情**
- **🏷️ 命名空间**: {{ $alert.labels.namespace }}
- **📡 实例名称**: {{ $alert.labels.pod }}
- **🌐 实例地址**: {{ $alert.labels.pod_ip }}
- **🖥️ 实例节点**: {{ $alert.labels.node }}
- **🔄 实例控制器类型**: {{ $alert.labels.owner_kind }}
- **🔧 实例控制器名称**: {{ $alert.labels.owner_name }}
---
📝 **告警描述**
{{ $alert.annotations.message }}{{ $alert.annotations.summary }}{{ $alert.annotations.description }}
---
🚀 **快速操作**
- **[点我屏蔽该告警]({{ $alertmanagerURL }}/#/silences/new?filter=%7B{{ SplitString $urimsg 0 -3 }}%7D)**
- **[点击我查看 Grafana 监控面板]({{ $grafanaURL }})**
---
📊 **建议操作**
1. 检查 Pod 日志，确认是否有异常。
2. 检查节点 {{ $alert.labels.node }} 的资源使用情况，确保没有资源瓶颈。
3. 如果问题持续，考虑重启 Pod 或节点。
---
📅 **告警时间线**
- **首次触发**: {{ GetCSTtime $alert.startsAt }}
{{ if eq $alert.status "resolved" }}
- **结束时间**: {{ GetCSTtime $alert.endsAt }}
{{ end }}
---
📞 **联系支持**
如有疑问，请联系 Kubernetes 运维团队或查看相关文档。
---
{{ if eq $alert.status "resolved" }}
**✅ 告警已恢复，请确认业务正常运行！**
{{ else }}
**🔔 请及时处理，避免影响业务正常运行！**
{{ end }}
---
{{ end -}}