# Walk Tracker Backend

一个零依赖的走路打卡后端，适合先做 MVP：今日打卡、记录步数、自动估算公里数、查询过去 7 天记录和统计。

## 运行

```bash
cd walk_tracker_backend
python3 app.py
```

默认地址：

```text
http://127.0.0.1:8000
```

浏览器打开这个地址就是前端页面；接口也挂在同一个服务上。

手机访问时，让手机和电脑连接同一个 Wi-Fi，然后打开电脑局域网地址，例如：

```text
http://192.168.0.118:8000/
```

页面已经支持 PWA。手机浏览器打开后，可以通过浏览器菜单添加到主屏幕。

页面带有轻量登录保护：用户需要输入姓名并通过安全图验证。登录后，运动记录会按姓名对应的用户隔离保存。

数据会保存在：

```text
walk_tracker_backend/data/walk_records.sqlite3
```

## 接口

### 健康检查

```bash
curl http://127.0.0.1:8000/health
```

### 今日记录

```bash
curl http://127.0.0.1:8000/records/today
```

### 今日打卡

```bash
curl -X POST http://127.0.0.1:8000/records/check-in \
  -H "Content-Type: application/json" \
  -d '{"steps":8000,"stride_meters":0.7,"note":"晚饭后散步"}'
```

返回里的 `distance_km` 会自动按这个公式计算：

```text
steps * stride_meters / 1000
```

### 查询过去 7 天

```bash
curl "http://127.0.0.1:8000/records?days=7"
```

没有打卡的日期也会返回，前端可以直接渲染 7 个日期格子。

### 查询 7 天统计

```bash
curl "http://127.0.0.1:8000/stats?days=7"
```

会返回：

- `checked_in_days`：打卡天数
- `missed_days`：未打卡天数
- `total_steps`：总步数
- `total_distance_km`：总公里数
- `average_steps`：日均步数
- `streak_days`：截至今天的连续打卡天数
- `records`：过去 N 天每日记录

### 修改某天记录

```bash
curl -X PUT http://127.0.0.1:8000/records/2026-05-18 \
  -H "Content-Type: application/json" \
  -d '{"checked_in":true,"steps":9000,"stride_meters":0.7}'
```

### 删除某天记录

```bash
curl -X DELETE http://127.0.0.1:8000/records/2026-05-18
```

## 前端接入建议

先调用 `GET /stats?days=7`，因为它同时包含统计数字和每日记录。用户点「今日打卡」时调用 `POST /records/check-in`，成功后重新拉一次 `GET /stats?days=7` 刷新页面。

## 测试

```bash
cd walk_tracker_backend
python3 -m unittest
```
