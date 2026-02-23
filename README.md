# Hyperliquid MCP Server

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that provides **real-time data access** to the [Hyperliquid](https://hyperliquid.xyz/) decentralized exchange.

No API key required — all endpoints are public and read-only.

---

## Quick Start

### Option 1: `uvx` — 零安装，直接运行（推荐）

> 需要先安装 [uv](https://docs.astral.sh/uv/getting-started/installation/)

```bash
uvx --from git+https://github.com/YOUR_USERNAME/hyperliquid-mcp.git hyperliquid-mcp
```

### Option 2: `pip` — 从 GitHub 安装

```bash
pip install git+https://github.com/YOUR_USERNAME/hyperliquid-mcp.git
hyperliquid-mcp
```

### Option 3: 本地开发

```bash
git clone https://github.com/YOUR_USERNAME/hyperliquid-mcp.git
cd hyperliquid-mcp
pip install -e .
hyperliquid-mcp
```

> ⚠️ 请将 `YOUR_USERNAME` 替换为你的 GitHub 用户名。

---

## 在 MCP 客户端中使用

### Claude Desktop

编辑配置文件：
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

**方式 A — uvx（推荐，无需预安装）：**

```json
{
  "mcpServers": {
    "hyperliquid": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/YOUR_USERNAME/hyperliquid-mcp.git",
        "hyperliquid-mcp"
      ]
    }
  }
}
```

**方式 B — 本地克隆后使用：**

```json
{
  "mcpServers": {
    "hyperliquid": {
      "command": "python",
      "args": ["/absolute/path/to/hyperliquid-mcp/src/hyperliquid_mcp/server.py"]
    }
  }
}
```

### Claude Code

```bash
# 从 GitHub（推荐）
claude mcp add hyperliquid -- uvx --from git+https://github.com/YOUR_USERNAME/hyperliquid-mcp.git hyperliquid-mcp

# 或者本地路径
claude mcp add hyperliquid python /path/to/hyperliquid-mcp/src/hyperliquid_mcp/server.py
```

### Cursor

在项目根目录创建 `.cursor/mcp.json`：

```json
{
  "mcpServers": {
    "hyperliquid": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/YOUR_USERNAME/hyperliquid-mcp.git",
        "hyperliquid-mcp"
      ]
    }
  }
}
```

### Windsurf / Cline

配置方式类似，在对应的 MCP 配置文件中添加与上面相同的 JSON 块即可。

---

## 功能概览

共 **33 个只读工具**，覆盖 Hyperliquid Info API 的全部主要端点：

### 📊 市场数据
| 工具 | 说明 |
|------|------|
| `hyperliquid_get_all_mids` | 全币种当前中间价 |
| `hyperliquid_get_l2_book` | L2 订单簿快照（每侧最多20档） |
| `hyperliquid_get_candles` | K线/OHLCV 数据（1m ~ 1M） |

### 📈 永续合约
| 工具 | 说明 |
|------|------|
| `hyperliquid_get_perp_meta` | 永续交易对元数据、保证金表 |
| `hyperliquid_get_perp_meta_and_asset_ctxs` | 元数据 + 标记价/资金费率/OI 等 |
| `hyperliquid_get_funding_history` | 历史资金费率 |
| `hyperliquid_get_predicted_fundings` | 多交易所预测资金费率 |
| `hyperliquid_get_perp_dexs` | 所有永续 DEX 列表 |

### 💱 现货
| 工具 | 说明 |
|------|------|
| `hyperliquid_get_spot_meta` | 现货代币详情与配置 |
| `hyperliquid_get_spot_meta_and_asset_ctxs` | 现货元数据 + 实时价格/成交量 |

### 👤 用户账户
| 工具 | 说明 |
|------|------|
| `hyperliquid_get_open_orders` | 当前挂单 |
| `hyperliquid_get_frontend_open_orders` | 挂单（含前端元数据） |
| `hyperliquid_get_user_fills` | 最近成交（最多2000条） |
| `hyperliquid_get_user_fills_by_time` | 按时间范围查成交 |
| `hyperliquid_get_clearinghouse_state` | 永续账户摘要与持仓 |
| `hyperliquid_get_spot_clearinghouse_state` | 现货余额 |
| `hyperliquid_get_order_status` | 按 OID/CLOID 查订单状态 |
| `hyperliquid_get_historical_orders` | 历史订单（最多2000条） |
| `hyperliquid_get_user_funding` | 资金费率支付历史 |
| `hyperliquid_get_user_rate_limit` | API 速率限制 |
| `hyperliquid_get_user_role` | 账户角色 |
| `hyperliquid_get_portfolio` | 组合表现历史 |
| `hyperliquid_get_user_fees` | 费率详情与折扣 |
| `hyperliquid_get_referral` | 推荐信息与奖励 |
| `hyperliquid_get_sub_accounts` | 子账户详情 |

### 🏦 Vault
| 工具 | 说明 |
|------|------|
| `hyperliquid_get_vault_details` | Vault 详情、APR、追随者 |
| `hyperliquid_get_user_vault_equities` | 用户 Vault 权益 |

### 🥩 质押
| 工具 | 说明 |
|------|------|
| `hyperliquid_get_delegations` | 质押委托 |
| `hyperliquid_get_delegator_summary` | 质押摘要 |
| `hyperliquid_get_delegator_rewards` | 质押奖励历史 |

### 🏦 借贷
| 工具 | 说明 |
|------|------|
| `hyperliquid_get_borrow_lend_user_state` | 用户借贷状态 |
| `hyperliquid_get_borrow_lend_reserve_state` | 单代币储备金状态 |
| `hyperliquid_get_all_borrow_lend_reserve_states` | 全部储备金状态 |

---

## 通用参数

所有工具支持：
- **`network`**: `"mainnet"`（默认）或 `"testnet"`
- **`response_format`**: `"markdown"`（默认，人类可读）或 `"json"`（原始数据）

需要用户地址的工具：
- **`user`**: 42 字符以太坊地址（例如 `0x1234...abcd`）

> ⚠️ 请使用实际的主账户/子账户地址，不要使用 Agent Wallet 地址。

### 资产命名规则

- **永续**: 使用 `meta` 返回的 coin 名称，如 `"BTC"`, `"ETH"`
- **现货**: PURR 使用 `"PURR/USDC"`，其余使用 `"@{index}"`，如 HYPE 为 `"@107"`
- **HIP-3**: 加 dex 前缀，如 `"xyz:XYZ100"`

---

## 示例对话

```
用户: "Hyperliquid 上 BTC 当前价格是多少？"
→ 调用 hyperliquid_get_all_mids

用户: "看一下 ETH 的订单簿"
→ 调用 hyperliquid_get_l2_book(coin="ETH")

用户: "过去24小时 BTC 的1小时K线"
→ 调用 hyperliquid_get_candles(coin="BTC", interval="1h", ...)

用户: "当前各币种的资金费率是多少？"
→ 调用 hyperliquid_get_perp_meta_and_asset_ctxs

用户: "查看地址 0xabc... 的持仓"
→ 调用 hyperliquid_get_clearinghouse_state(user="0xabc...")

用户: "目前借贷市场的利率情况？"
→ 调用 hyperliquid_get_all_borrow_lend_reserve_states
```

---

## 项目结构

```
hyperliquid-mcp/
├── src/
│   └── hyperliquid_mcp/
│       ├── __init__.py
│       └── server.py          # MCP 服务器主文件（所有工具定义）
├── pyproject.toml              # 包配置 & 依赖
├── README.md
├── LICENSE
└── .gitignore
```

## API 参考

本服务封装了 [Hyperliquid Public API](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api)：
- **Mainnet**: `https://api.hyperliquid.xyz/info`
- **Testnet**: `https://api.hyperliquid-testnet.xyz/info`
- 所有请求均为 `POST` + JSON body，无需 API Key

## License

MIT
