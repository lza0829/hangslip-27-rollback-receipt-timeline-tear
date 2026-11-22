# 衣票墙（hangslip）

收衣贴号 → 工序推进 → 取衣核销关账 → 超期/丢失隔离互证。

- 前端 http://127.0.0.1:6200
- API http://127.0.0.1:11200

## 工序时间线口径（全局唯一）

本系统只贯彻一套架构：**可倒回一档**。

- 工序链：`已收 → 水洗 → 烘干 → 熨烫 → 待取 → 已取`（前进允许跳步）。
- 倒回仅允许回到**相邻上一档**：`熨烫 → 烘干`、`待取 → 熨烫` 等；首档「已收」无上一档，拒绝。
- **硬边界**：`已取`、`超期隔离`、`丢失隔离` 为终态，任何倒回/推进请求一律 409，现行态不得拨回。
- `process_events` 只追加，每条事件带 `kind`：`收衣 / 推进 / 倒回 / 取衣 / 隔离`。
- 挂牌现行态、待取页可见性、在途水位、总览工序分布**均可由含倒回的事件链重放得到**，
  不存在「回执已回上一档但事件链只前进」或「已取票被倒回待取」的口径分裂。
- 所有写操作走 `BEGIN IMMEDIATE` 事务，读现行态→校验→落库串行化；
  并发倒回与取衣不可能产生双终态（20 轮竞争测试覆盖）。
- 纠错靠倒回事件本身留痕；向前跳步不在本需求范围内。

`GET /api/链路自检` 返回事件链重放态 vs 挂牌现行态 vs 水位的一致性，分裂即非「一致」。

## 接口

- `POST /api/挂牌/{ticket_no}/倒回`，body：`{"operator": "工序员", "note": ""}`
- 其余接口（开票/推进/取衣/隔离/日闸/总览）保持不变。

## 本地开发

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 11200

cd ..\frontend
npm install
npm run dev
```

## 测试

```bash
cd backend
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests/ -q
```

覆盖：倒回相邻规则与首档拒绝、已取/隔离硬边界、待取页可见性联动、
事件链重放与水位/总览联动、日闸封锁、旧库 `kind` 列迁移、
倒回×取衣并发无双终态、以及对篡改数据的自检捕获。
