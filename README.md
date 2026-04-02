# ECHA Chemical Data MCP Server

欧洲化学品管理局 (ECHA) 数据查询 MCP Server，提供 9 个工具覆盖物质信息、CLP 分类、REACH 注册分类和毒理数据。

## 🔧 Tools 一览

| Tool | 描述 | 数据源 |
|------|------|--------|
| `echa_get_substance_info` | 物质基本信息（CAS、EC、名称） | REST API |
| `echa_list_dossiers` | REACH 注册卷宗列表 | REST API |
| `echa_get_clp_classification` | CLP 通报分类（行业自主分类） | REST API |
| `echa_get_harmonised_classification` | 协调分类（Annex VI 官方分类） | REST API |
| `echa_get_reach_ghs` | REACH 卷宗 GHS 分类（Section 2.1） | HTML 解析 |
| `echa_get_reach_pbt` | REACH 卷宗 PBT 评估（Section 2.3） | HTML 解析 |
| `echa_get_toxicology_summary` | 毒理概述 + DN(M)ELs（快速） | HTML 解析 |
| `echa_get_toxicology_studies` | 毒理个体研究记录（可按章节过滤） | HTML 解析 |
| `echa_get_toxicology_full` | 完整毒理数据（慢，最多 400 个 Study） | HTML 解析 |

## 📚 Resources

| Resource URI | 描述 |
|---|---|
| `echa://hcode-mapping` | GHS 危害分类 → H 代码映射表（Markdown） |
| `echa://hcode-mapping-json` | H 代码映射表（JSON） |

## 🚀 Quick Start

### 安装依赖

```bash
cd echa_mcp
pip install -e .
```

### 启动服务（SSE 模式）

```bash
python -m echa_mcp.server
# 或
echa-mcp
```

默认启动 SSE 服务，监听端口用于远程客户端连接。

### 配置到 MCP 客户端

```json
{
  "mcpServers": {
    "echa": {
      "url": "http://your-server:8000/sse"
    }
  }
}
```

## 📋 示例用法

### 查询甲醛 (Formaldehyde) 信息

```
substance_index: 100.000.002
```

工具调用顺序推荐:
1. `echa_get_substance_info` → 获取 CAS (50-00-0)、EC、名称
2. `echa_get_harmonised_classification` → 查看协调分类
3. `echa_get_clp_classification` → 查看行业通报分类
4. `echa_get_toxicology_summary` → 快速查看毒理概述和 DNEL 值

## 🏗 技术架构

```
echa_mcp/
├── server.py              # FastMCP 入口，注册 tools + resources
├── clients/
│   └── echa_client.py     # 异步 HTTP 客户端（httpx）
├── tools/                 # MCP tool 实现
│   ├── substance.py       # 物质信息 + 卷宗列表
│   ├── clp_classification.py
│   ├── harmonised_classification.py
│   ├── reach_classification.py
│   └── toxicology.py
├── parsers/               # HTML 解析器
│   ├── common.py          # 共享解析工具
│   ├── section2_parser.py # Section 2 GHS/PBT
│   └── section7_parser.py # Section 7 毒理
├── models/                # Pydantic 输入模型
│   ├── substance.py
│   ├── classification.py
│   └── toxicology.py
└── data/
    └── hcode_mapping.py   # H-code 映射表
```

## 依赖

- `mcp[cli]` >= 1.0.0 (MCP Python SDK)
- `httpx` >= 0.27.0 (异步 HTTP)
- `beautifulsoup4` >= 4.12.0 (HTML 解析)
- `pydantic` >= 2.0.0 (输入验证)
