# موتور معاملاتی هوشمند چند-ایجنته والکس (`wallex-agentic-trader`)
### معماری Hybrid Graph-Harness مجهز به مدل بنیادین سری زمانی **Kronos**، موتور تصمیم‌گیری فراسریع **System-1 (`Jev` / `Mizan-4B` / `Laya` / `Kev`)** و تحلیلگر کوانت **System-2** برای چالش صرافی والکس در هکاتون Agentic AI استارکوچ

---

## فهرست مطالب (منطبق بر ۵ محور الزامی داوری فنی والکس — ۳۰۰ امتیاز)
1. [محور اول: معماری و منطق اصلی الگوریتم (Hybrid Graph-Harness + System-1/System-2 + Kronos)](#1-محور-اول-معماری-و-منطق-اصلی-الگوریتم)
2. [محور دوم: نحوه استفاده واقعی از هوش مصنوعی و ابزارهای دوگانه والکس (Wallex REST/WS API + Wallex MCP)](#2-محور-دوم-نحوه-استفاده-از-هوش-مصنوعی-و-ابزارهای-والکس)
3. [محور سوم: شرایط کمی و ایجنتیک تصمیم‌گیری برای خرید، فروش و تسویه تومانی](#3-محور-سوم-شرایط-تصمیمگیری-برای-خرید-و-فروش)
4. [محور چهارم: روش مدیریت سرمایه، گیت قطعی ریسک (Deterministic Risk Gate) و حاکمیت هوش مصنوعی (AI Governance)](#4-محور-چهارم-روش-مدیریت-سرمایه-ریسک-و-حاکمیت-هوش-مصنوعی)
5. [محور پنجم: راهنمای اجرای مجدد (Reproducibility)، نتایج Backtesting، Shadow Testing و ممیزی `decision_logs.jsonl`](#5-محور-پنجم-امکان-اجرای-مجدد-و-ارزیابی-عملکرد-الگوریتم)
6. [داشبورد Generative UI (Chat Plus با Next.js + shadcn/ui + CopilotKit AG-UI/A2UI) و سناریوی ویدیوی دموی ۵ دقیقه‌ای](#6-داشبورد-generative-ui-و-سناریوی-ویدیوی-دموی-۵-دقیقهای)

---

## ۱. محور اول: معماری و منطق اصلی الگوریتم

این سیستم یک **موتور معاملات الگوریتمی اسپات (Spot) ۱۰۰٪ خودکار، تکرارپذیر و قابل ممیزی** است که به صورت اختصاصی برای مدیریت سرمایه اولیه **`5,000,000` تومان (طرح اعتبار معاملاتی والکس)** در بازه ۷۲ ساعته هکاتون طراحی شده است.

### چالش معماری: چرا ترکیب `StateGraph` (LangGraph) و `ReAct Harness`؟
استفاده از یک حلقه `ReAct` خام در معاملات مالی ریسک فراخوانی جابه‌جای ابزارها، افتادن در حلقه بی‌نهایت هنگام خطای شبکه و نقض قوانین ریسک را به همراه دارد. از سوی دیگر، یک اسکریپت صلب مبتنی بر شرط‌های `if/else` فاقد درک پویا از تغییر رژیم بازار بوده و ۳۵ امتیاز معیار **«استفاده واقعی از Agentic AI»** را از دست می‌دهد.

در معماری **Hybrid Graph-Harness** این پروژه:
- **کنترل جریان کلان و قطعی (Macro-Orchestration)** بر عهده یک گراف ۸ ایستگاهی در **LangGraph (`StateGraph`)** مجهز به `MemorySaver` و مکانیزم توقف کلان `interrupt()` است.
- **تفکیک شناختی System-1 و System-2** مانع از اتلاف زمان (Latency) و مصرف توکن در سیکل‌های بدون سیگنال می‌شود:
  - **ایستگاه پیش‌بینی کمی سری زمانی (`KronosForecastAgent`)**: مبتنی بر مدل بنیادین کندل‌استیک **[shiyu-coder/Kronos](https://github.com/shiyu-coder/Kronos)** (`NeoQuasar/Kronos-small` + `NeoQuasar/Kronos-Tokenizer-base`) که توزیع احتمالی ۱۲ کندل آینده (`OHLCV`)، بازده مورد انتظار (`expected_return_pct`)، احتمال سود خالص پس از کسر کارمزد (`upside_probability`) و بدترین افت پیش‌بینی‌شده (`predicted_low_min`) را استخراج می‌کند.
  - **موتور تصمیم‌گیری فراسریع System-1 (`System1RegimeRouterNode`)**: کلاینت واحد بر پایه پروتکل `/v1/systemone` که با پشتیبانی از ۴ بک‌اند **[Jev (MetisAI TypeSafe)](https://docs.metisai.ir/api/wrapper/typesafe)**، **[Mizan-4B](https://huggingface.co/xmanii/Mizan-4B)** (مدل تصمیم‌گیری بومی و فارسی‌محور روی Qwen3.5-4B)، **[Laya](https://github.com/NandhaKishorM/laya)** (روتر غیرخودهمبسته ۳۳ میلی‌ثانیه‌ای LangGraph) و **[Kev](https://github.com/jaredpalmer/kev)**، در یک پاس رو به جلو (زیر ۵۰ میلی‌ثانیه) احتمالات کالیبره‌شده رژیم بازار (`BULL_TREND`, `RANGE_SCALP`, `HIGH_VOL_PUMP_DUMP`, `NIGHT_THIN_LIQUIDITY`)، گیت اقدام و مهارت مورد نیاز (`SKILL.md`) را تعیین می‌کند.
  - **مغز تحلیلگر کوانت System-2 (`System2QuantAnalystAgent`)**: مبتنی بر **DeepSeek V4.1 Flash** در یک **ReAct Harness** مهندسی‌شده که تنها به **۳ مگا-تول (Mega-Tools)**، مهارت‌های بارگذاری تدریجی (`skills/*/SKILL.md`) و حافظه کاری/اپیزودیک فایل‌محور دسترسی دارد و پیشنهاد ساختاریافته معامله (`TradeProposal`) را به همراه استدلال کامل فارسی و انگلیسی تولید می‌نماید.

```text
[EXECUTION_MODE: BACKTEST | SHADOW | LIVE]
        │
        ▼
[1. MarketScannerNode (Async Python + Wallex REST/WS API: https://api.wallex.ir)]
   - دریافت /v1/markets، /v1/depth، /v1/trades و کندل‌های /v1/udf/history
   - محاسبه آلفا/بتا/گامای ریزساختار، OrderBook Imbalance (OBI)، Spread، RSI و ATR
   - فیلتر کردن ۲ تا ۳ جفت‌ارز برتر مجاز اعتبار معاملاتی دارای ناهنجاری حجمی/قیمتی
        │
        ├───────────────────────────────────────────┐
        ▼                                           ▼
[2A. KronosForecastNode (Quantitative)]     [2B. SentimentGuardNode (Isolated Subagent)]
   - مدل: shiyu-coder/Kronos                   - رصد ایزوله اخبار/تلگرام بدون دسترسی به .env
     (NeoQuasar/Kronos-small + Tokenizer)      - فیلتر Prompt Injection و امتیازدهی با Mizan-4B
   - پیش‌بینی چندگامی کندل‌های OHLCV،            - بدون دسترسی به هیچ ابزار معاملاتی (شکستن
     E[Return]، Upside Prob و کمینه قیمت         مثلث مرگبار سایمون ویلسون)
        │                                           │
        └─────────────────────┬─────────────────────┘
                              ▼
[3. System1RegimeRouterNode (Unified /v1/systemone Decision Engine)]
   - بک‌اند ابری: Jev (MetisAI TypeSafe) | بک‌اندهای لوکال: Mizan-4B، Laya (33ms)، Kev
   - خروجی احتمالات کالیبره‌شده برای:
     * market_regime: BULL_TREND | RANGE_SCALP | HIGH_VOL_PUMP_DUMP | NIGHT_THIN_LIQUIDITY
     * action_gate: PROCEED_TO_SYSTEM2 | FAST_HOLD | EMERGENCY_LIQUIDATE
     * active_skill: orderbook_scalp | risk_management | toman_settlement
                              │
                              ▼
[4. System2QuantAnalystNode (ReAct Harness + DeepSeek V4.1 Flash / LLM)]
   - مجهز به ۳ مگا-تول (Mega-Tools) + بارگذاری تدریجی مهارت‌ها (Progressive Disclosure SKILL.md)
   - ترکیب پیش‌بینی Kronos + عدم تقارن اردربوک + حافظه کاری (active_positions_plan.json)
   - تولید TradeProposal ساختاریافته + استدلال شفاف فارسی (reasoning_log_fa)
                              │
                              ▼
[5. DeterministicRiskGateNode (100% Pure Python Guardrail + Kev/Laya Policy Check)]
   - ممیزی قطعی ۸ قانون خط قرمز: لیست مجاز اعتبار معاملاتی، سقف ۱۸٪ هر سفارش (<=900,000 TMN)،
     حداقل ۴۰٪ ذخیره نقد تومانی (>=2,000,000 TMN)، حد ضرر پویا (۱.۵٪ تا ۲٪)، Net R/R >= 2.0،
     جلوگیری از معامله با خود (Self-Trade Prevention)، تطبیق نقدینگی شبانه، مدارقطع‌کن ۳٪ افت
     روزانه و گیت تسویه اجباری ۱۰۰٪ به تومان در ۴ ساعت پایانی چالش
                              │
                              ▼
[6. MacroHITLInterruptNode (LangGraph interrupt() + MemorySaver Checkpointer)]
   - عبور ۱۰۰٪ خودکار برای معاملات خرد (رعایت ممنوعیت مطلق معامله دستی)
   - توقف صرفاً در رویدادهای حاکمیتی کلان: ارتقای Shadow به Live، تغییر SKILL یا ریست مدارقطع‌کن
                              │
                              ▼
[7. ExecutionAndLoggerNode (Wallex MCP + REST Fallback + Stale Price Refresh)]
   - رفرش لحظه‌ای best_bid / best_ask دفترچه سفارشات جهت جلوگیری از Stale Price (آستانه ۰.۴٪)
   - اجرای سفارش از طریق Wallex MCP (در حالت LIVE) یا MockOrderBookMatcher (در حالت SHADOW/BACKTEST)
   - ثبت لاگ تغییرناپذیر در فایل logs/decision_logs.jsonl
                              │
                              ▼
[8. EvaluatorAndCompactionNode (Evaluator-Optimizer Reflection + OpenCode Compaction)]
   - کالبدشکافی سیکل‌های بسته‌شده به تومان و ثبت درس‌آموخته در memory/learned_trading_rules.md
   - فشرده‌سازی خودکار تاریخچه پیام‌ها هنگام عبور از آستانه ۱۲,۰۰۰ توکن
```

---

## ۲. محور دوم: نحوه استفاده از هوش مصنوعی و ابزارهای والکس

### ۲.۱. معماری دولایه ارتباط با صرافی والکس (`Wallex REST/WS API` + `Wallex MCP`)
طبق راهنمایی تیم فنی مارکت‌میکینگ والکس و مستندات رسمی [developers.wallex.ir](https://developers.wallex.ir/docs):
1. **لایه اول — دریافت پرتکرار و کم‌تاخیر داده‌های بازار (`src/wallex/rest_client.py`):**
   - فراخوانی ناهمگام (`httpx.AsyncClient`) اندپوینت‌های `GET /v1/markets` (مشخصات بازارها و دقت اعشار `tick_size` / `step_size`)، `GET /v1/depth?symbol={SYMBOL}` (عمق دفترچه سفارشات لحظه‌ای)، `GET /v1/trades?symbol={SYMBOL}` (جریان معاملات اخیر) و `GET /v1/udf/history` (کندل‌های تاریخی OHLCV).
   - شنونده زنده WebSocket (`wss://api.wallex.ir/ws`) روی کانال‌های `{symbol}@depth` و `{symbol}@trade` جهت به‌روزرسانی کش محلی قیمت‌ها در کسری از ثانیه.
2. **لایه دوم — عملیات حساب و سفارش‌گذاری ایجنتیک با Wallex MCP (`src/wallex/mcp_client.py`):**
   - اتصال به سرور **Wallex MCP** (با پشتیبانی از فراخوانی مستقیم اندپوینت‌های `/v1/account/balances`، `/v1/account/fee`، `/v1/account/openOrders` و `POST /v1/account/orders` با هدر `x-api-key`).
   - **مکانیزم حیاتی Stale Price Refresh**: از آنجا که استدلال مدل هوش مصنوعی ممکن است چند صد میلی‌ثانیه زمان ببرد، ماژول `WallexMCPClient.place_order` دقیقاً در لحظه ارسال سفارش، آخرین `best_bid` و `best_ask` دفترچه سفارشات را مجدداً استعلام می‌کند؛ اگر قیمت بیش از `MAX_PRICE_DRIFT_PCT = 0.40%` جابه‌جا شده باشد، سفارش با قیمت کهنه مسدود یا به قیمت امن رفرش می‌شود.

### ۲.۲. مهندسی هارنس (Harness Engineering) و بهینه‌سازی پنجره محتوایی
برای جلوگیری از چهار عارضه پنجره محتوایی (**Poisoning, Confusion, Conflict, Distraction**):
- **۳ مگا-تول دسته‌بندی‌شده (`src/harness/mega_tools.py`)**: به جای معرفی ده‌ها اندپوینت مجزا که کانتکست مدل را پر می‌کنند، تنها ۳ مگا-تول با اسکیمای دقیق Pydantic به ایجنت معرفی شده‌اند:
  1. `wallex_market_intelligence`: دریافت ریزساختار اردربوک، پیش‌بینی کندل Kronos، ضرایب آلفا/بتا/گاما و وضعیت بازارهای مجاز.
  2. `wallex_trade_executor`: ثبت پیشنهاد سفارش (`propose_order`)، لغو سفارش باز، استعلام موجودی/سفارش‌های باز و تسویه کامل به تومان (`liquidate_all_to_toman`).
  3. `agent_memory_and_skills`: بارگذاری فایل‌های مهارت (`load_skill_markdown`)، خواندن/به‌روزرسانی برنامه پوزیشن‌های باز و ثبت قواعد یادگرفته‌شده.
- **افشای تدریجی مهارت‌ها (`skills/*/SKILL.md` و `src/harness/skill_loader.py`)**: در سیستم‌پرامپت اولیه فقط نام و توضیح یک‌خطی مهارت‌ها قرار می‌گیرد و متن کامل فرمول‌ها (`orderbook_scalp`, `risk_management`, `toman_settlement`) تنها در صورت نیاز بارگذاری می‌شود.
- **حافظه سهلایه‌ای و حلقه خودآموز (`src/harness/memory_manager.py` و `compaction.py`)**:
  - حافظه کوتاه‌مدت درونسشنی با `MemorySaver` در LangGraph.
  - حافظه کاری فایل‌محور در `memory/active_positions_plan.json` برای حفظ برنامه خروج هر پوزیشن باز در طول ۷۲ ساعت.
  - حافظه اپیزودیک خودآموز در `memory/learned_trading_rules.md` به همراه فشرده‌ساز خودکار کانتکست به سبک OpenCode.

---

## ۳. محور سوم: شرایط تصمیم‌گیری برای خرید و فروش

تصمیمات خرید و فروش بر پایه همگرایی سه لایه کمی و ایجنتیک اتخاذ می‌شوند (`src/wallex/microstructure.py` + `src/models/kronos_forecaster.py` + `skills/orderbook_scalp/SKILL.md`):

### ۳.۱. شاخص‌های کمی ریزساختار بازار (Microstructure Alphas)
1. **عدم تقارن فشار دفترچه سفارشات (OrderBook Imbalance - OBI)** در ۵ سطح برتر:
   $$\text{OBI}_5 = \frac{\sum_{i=1}^{5} V_{\text{bid}, i} - \sum_{i=1}^{5} V_{\text{ask}, i}}{\sum_{i=1}^{5} V_{\text{bid}, i} + \sum_{i=1}^{5} V_{\text{ask}, i}} \in [-1, +1]$$
2. **آلفای ریزساختار ($\alpha_{\text{micro}}$)** (فشار قیمت میانی وزنی حجم نسبت به قیمت میانی ساده):
   $$P_{\text{micro}} = \frac{P_{\text{bid}, 1} \cdot V_{\text{ask}, 1} + P_{\text{ask}, 1} \cdot V_{\text{bid}, 1}}{V_{\text{bid}, 1} + V_{\text{ask}, 1}}, \quad \alpha_{\text{micro}} = \frac{P_{\text{micro}} - P_{\text{mid}}}{P_{\text{mid}}} \times 10000 \text{ (bps)}$$
3. **بتای جریان سفارشات ($\beta_{\text{flow}}$)** از روی معاملات اخیر (`/v1/trades`) و **گامای شتاب حجم کندل ($\gamma_{\text{mom}}$)**.

### ۳.۲. شروط ورود به معامله خرید (`BUY`)
سفارش خرید (`LIMIT` روی `best_bid * (1 + 0.0002)` جهت بهره‌مندی از کارمزد Maker و حذف هزینه اسپرد) تنها زمانی صادر می‌شود که:
- $\text{OBI}_5 \ge +0.18$ و $\alpha_{\text{micro}} > +0.5 \text{ bps}$ (برتری تقاضا در دفترچه سفارشات).
- اسپرد لحظه‌ای دفترچه سفارشات $\text{Spread (\%)} \le 0.35\%$.
- پیش‌بینی ۱۲ کندلی مدل **Kronos** نشان دهد: `expected_return_pct >= +0.85%` و `upside_probability >= 0.58`.
- شاخص `RSI(14)` در محدوده اشباع خرید نباشد ($\text{RSI}_{14} < 68$).
- نسبت سود خالص مورد انتظار به ریسک پس از کسر دو طرف کارمزد والکس ($2 \times 0.25\%$) و اسپرد، حداقل **`expected_net_rr >= 2.0`** باشد.

### ۳.۳. شروط خروج، حد سود (`SELL`) و تسویه اجباری به تومان (`LIQUIDATE_ALL_TO_TOMAN`)
- **حد ضرر پویا (Dynamic Stop-Loss)**: تنظیم خودکار بین `1.5%` تا `2.0%` زیر قیمت ورود بر مبنای $\max(1.5 \times \text{ATR}, \text{Kronos Predicted Low})$.
- **خروج هوشمند تحلیلگر**: هرگاه روی یک پوزیشن باز، $\text{OBI}_5 < -0.22$ شود یا پیش‌بینی Kronos منفی گردد (`expected_return_pct < -0.30%`) یا قیمت به `take_profit` برسد، سفارش فروش صادر می‌شود.
- **بستن چرخه به تومان (100% Realized PnL in TMN)**: مطابق قانون صریح چالش («سود یا ضرر حاصل‌شده باید در تومان محقق شود و نباید در پایان دوره دارایی به صورت کوین باشد»)، در ۴ ساعت پایانی چالش (`hours_remaining_in_challenge <= 4.0`) هرگونه خرید جدید مسدود شده و کلیه موجودی‌های کوینی و تتری به تومان نقد می‌شوند.

---

## ۴. محور چهارم: روش مدیریت سرمایه، ریسک و حاکمیت هوش مصنوعی

### ۴.۱. گیت قطعی مدیریت ریسک (`src/governance/risk_gate.py`)
نود پایتونی `DeterministicRiskGateNode` پیش از اجرای هر سفارش، ۸ شرط زیر را بدون دخالت LLM به صورت ۱۰۰٪ قطعی اعمال می‌کند:

| ردیف | قانون مدیریت ریسک و انضباطی | پارامتر اجرایی روی سرمایه ۵,۰۰۰,۰۰۰ تومان | رفتار گیت ریسک در صورت نقض |
| :--- | :--- | :--- | :--- |
| **۱** | **لیست سفید بازارهای مجاز** | `ALLOWED_CREDIT_MARKETS` (`USDTTMN`, `BTCTMN`, `ETHTMN`, `SOLTMN`, ...) | رد فوری سفارش (`REJECT`) |
| **۲** | **سقف کسری حجم هر سفارش** | حداکثر **`18%`** کل پرتفوی (**حداکثر `900,000` تومان** در هر سفارش) | تعدیل خودکار حجم (`adjusted_quantity`) به سقف ۱۸٪ |
| **۳** | **ذخیره نقدی احتیاطی تومانی** | حفظ حداقل **`40%`** نقد تومانی (**حداقل `2,000,000` تومان** آزاد) | کاهش حجم سفارش یا رد در صورت نبود نقدینگی بالای ۴۰٪ |
| **۴** | **حد ضرر پویا و ریسک به ریوارد** | حد ضرر اجباری **`1.5%` تا `2.0%`** (حداکثر ریسک ~۱۸,۰۰۰ تومان) و **`Net R/R >= 2.0`** | اصلاح خودکار حد ضرر/سود یا رد سفارش‌های کم‌بازده |
| **۵** | **جلوگیری از معامله با خود (STP)** | بررسی `openOrders` حساب جهت عدم تداخل قیمت سفارش جدید با سفارش باز خود ایجنت | رد سفارش متداخل (`SELF_TRADE_PREVENTION`) |
| **۶** | **تطبیق نقدینگی شبانه** | ساعات `00:30` تا `07:00` تهران یا اسپرد بالای `0.35%` | نصف کردن سقف حجم سفارش (`9%` معادل ۴۵۰,۰۰۰ تومان) و تبدیل `MARKET` به `LIMIT` |
| **۷** | **مدارقطع‌کن افت سرمایه (Circuit Breaker)** | افت روزانه بیش از **`3.0%`** نسبت به سقف ارزش حساب (High-Water Mark) | توقف خرید و انتقال خودکار به وضعیت `SHADOW` (Cooldown) |
| **۸** | **تسویه اجباری پایان چالش به تومان** | `hours_remaining_in_challenge <= 4.0` | مسدودسازی کامل `BUY` و نقد کردن ۱۰۰٪ دارایی‌ها به تومان |

### ۴.۲. حاکمیت هوش مصنوعی (AI Governance) و شکستن «مثلث مرگبار» (`src/governance/security_guard.py`)
بر اساس اصول کارگاه AI Governance (گدار AI / تحلیل حادثه ۹ ثانیه Pocket.co) و چارچوب سایمون ویلسون:
1. **شکستن مثلث مرگبار (Breaking the Lethal Trifecta)**:
   - ساب‌ایجنت رصد اخبار (`SentimentGuardNode`) در محیط کاملاً ایزوله بدون دسترسی به `.env` و بدون دسترسی به ابزارهای معاملاتی اجرا می‌شود و متن ورودی را با فیلتر تشخیص Prompt Injection فارسی/انگلیسی پاک‌سازی می‌کند.
   - کلیدهای خصوصی (`WALLEX_API_KEY`, `METIS_API_KEY`, `LLM_API_KEY`) هرگز وارد پرامپت یا کانتکست مدل نمی‌شوند و دسترسی ابزار خواندن فایل به `.env` در سطح کد مسدود شده است.
2. **هویت اختصاصی و انقضای خودکار کلید (`AGENT_VIRTUAL_USER_ID=hackathon-wallex-agent`)**: بررسی مستمر `AGENT_KEY_EXPIRES_AT` پیش از هر سیکل معاملاتی.
3. **پروتکل بازنشستگی ایمن (`scripts/retire_agent.py`)**: لغو کلیه سفارش‌های باز، نقد کردن ۱۰۰٪ پرتفوی به تومان، تولید گزارش نهایی سود و زیان محقق‌شده و ایجاد قفل دائمی `logs/agent_retired.lock`.

---

## ۵. محور پنجم: امکان اجرای مجدد و ارزیابی عملکرد الگوریتم

### ۵.۱. ساختار کامل مخزن پروژه
```text
wallex-agentic-trader/
├── .env.example                       # قالب متغیرهای محیطی (بدون هیچ کلید واقعی)
├── .gitignore                         # مسدودسازی کامل .env و کش‌ها
├── pyproject.toml                     # وابستگی‌های استاندارد پایتون
├── docker-compose.yml                 # اجرای یکپارچه بک‌اند، فرانت‌اند و سرویس مدل لوکال
├── README.md                          # مستند فنی جامع ۵ محوری داوری + راهنمای اجرای مجدد
├── skills/                            # کتابخانه مهارت‌ها با افشای تدریجی (Progressive Disclosure)
│   ├── orderbook_scalp/SKILL.md
│   ├── risk_management/SKILL.md
│   └── toman_settlement/SKILL.md
├── memory/                            # حافظه کاری و اپیزودیک فایل‌محور هارنس
│   ├── active_positions_plan.json
│   └── learned_trading_rules.md
├── logs/                              # تحویلی الزامی لاگ تصمیمات به داوران
│   └── decision_logs.jsonl
├── evaluation_results/                # خروجی‌های اثبات فنی برای ۲۰ امتیاز تست
│   ├── backtest_report.json
│   └── shadow_test_summary.json
├── src/
│   ├── config.py                      # تنظیمات مرکزی، لیست بازارهای مجاز اعتبار معاملاتی و پارامترهای ریسک
│   ├── wallex/
│   │   ├── rest_client.py             # کلاینت کم‌تاخیر Wallex REST & WebSocket
│   │   ├── mcp_client.py              # کلاینت Wallex MCP Server + اجرای سفارش با Stale Price Refresh
│   │   └── microstructure.py          # محاسبه آلفا، بتا، گاما، OrderBook Imbalance، Spread و ATR
│   ├── models/
│   │   ├── kronos_forecaster.py       # ادغام مدل shiyu-coder/Kronos برای پیش‌بینی احتمالی کندل‌های OHLCV
│   │   └── system_one_engine.py       # آداپتور واحد /v1/systemone برای Jev (MetisAI)، Mizan-4B، Laya و Kev
│   ├── harness/
│   │   ├── mega_tools.py              # ۳ مگا-تول بهینه‌شده برای جلوگیری از Context Bloat
│   │   ├── skill_loader.py            # بارگذار داینامیک SKILL.md با بررسی allowed-tools
│   │   ├── memory_manager.py          # مدیریت حافظه کاری JSON و ژورنال خودآموز استراتژی
│   │   └── compaction.py              # فشرده‌ساز کانتکست سشن به سبک OpenCode
│   ├── governance/
│   │   ├── risk_gate.py               # گیت قطعی مدیریت ریسک، سقف سفارش ۱۸٪، Self-Trade Prevention و تسویه تومانی
│   │   └── security_guard.py          # ایزولاسیون سکرت‌ها، بررسی TTL کلید و محافظ Prompt Injection
│   ├── graph/
│   │   ├── state.py                   # تعریف کامل TradingState (TypedDict)
│   │   ├── nodes.py                   # پیاده‌سازی ۸ ایستگاه تخصصی گراف
│   │   └── workflow.py                # ساخت و کامپایل StateGraph با MemorySaver، interrupt و Langfuse
│   ├── testing/
│   │   ├── backtester.py              # موتور بک‌تست روی کندل‌های تاریخی والکس
│   │   └── shadow_engine.py           # موتور تطبیق سفارش مجازی (Shadow Testing) روی اردربوک زنده
│   └── api/
│       └── server.py                  # سرور FastAPI + اندپوینت AG-UI / CopilotKit برای اتصال به داشبورد فرانت‌اند
├── scripts/
│   ├── run_backtest.py                # اسکریپت اجرای بک‌تست تکرارپذیر برای داوران
│   ├── run_shadow.py                  # اسکریپت اجرای تست سایه در بازار زنده
│   ├── run_live.py                    # اسکریپت اجرای معاملات واقعی در حساب اختصاصی چالش
│   └── retire_agent.py                # اسکریپت تسویه نهایی به تومان، لغو سفارش‌ها و بازنشستگی ایجنت
└── frontend/                          # داشبورد Chat Plus مبتنی بر Next.js + shadcn/ui + CopilotKit (AG-UI)
    ├── package.json
    └── src/
        ├── app/page.tsx               # چیدمان Chat Plus (پنل چت ایجنت + داشبورد تحلیلی زنده والکس)
        └── components/genui/
            ├── TradeDecisionCard.tsx  # کارت نمایش سیگنال، پیش‌بینی Kronos و آکاردئون دلیل معامله
            ├── AgentGraphProgress.tsx # نمایشگر زنده وضعیت نودهای LangGraph
            ├── DynamicRegimeView.tsx  # رندرگر Declarative JSON مقایسه بازارها و ریسک پرتفوی
            └── HITLApprovalModal.tsx  # فرم تایید انسانی انتقال از Shadow به Live
```

### ۵.۲. دستورات گام‌به‌گام اجرای مجدد برای داوران (Reproducibility)

1. **آماده‌سازی محیط:**
   ```bash
   cp .env.example .env
   pip install -e .
   ```
2. **اجرای آزمون داده‌های تاریخی (Backtesting) و تولید گزارش آماری:**
   ```bash
   PYTHONPATH=. python3 scripts/run_backtest.py
   ```
   - خروجی کامل در فایل `evaluation_results/backtest_report.json` و لاگ تک‌تک تصمیمات در `logs/decision_logs.jsonl` ذخیره می‌شود.
3. **اجرای آزمون سایه (Shadow Testing) روی بازار زنده والکس بدون درگیر کردن پول واقعی:**
   ```bash
   PYTHONPATH=. python3 scripts/run_shadow.py --cycles 10
   ```
   - خروجی در `evaluation_results/shadow_test_summary.json` ثبت شده و پس از ۱۰ تصمیم معتبر، گیت `MacroHITLInterruptNode` آماده ارتقا به حالت `LIVE` می‌گردد.
4. **اجرای معاملات واقعی (Live Trading) روی حساب اختصاصی چالش:**
   ```bash
   EXECUTION_MODE=LIVE PYTHONPATH=. python3 scripts/run_live.py --cycles 50 --interval 60
   ```
5. **تسویه نهایی ۱۰۰٪ دارایی‌ها به تومان و بازنشستگی ایمن ایجنت در پایان هکاتون:**
   ```bash
   PYTHONPATH=. python3 scripts/retire_agent.py
   ```

---

## ۶. داشبورد Generative UI و سناریوی ویدیوی دموی ۵ دقیقه‌ای

برای نمایش شفاف منطق تصمیم‌گیری در ویدیوی دموی ۵ دقیقه‌ای الزامی، یک داشبورد مدرن به سبک **Chat Plus** با پشته **Next.js + Tailwind CSS + shadcn/ui + CopilotKit (`AG-UI` & Declarative `A2UI`)** در پوشه `frontend/` پیاده‌سازی شده است:
- **دقیقه ۰:۰۰ تا ۱:۰۰ (معماری و گاردریل‌های ریسک)**: نمایش زنده گراف ۸ ایستگاهی در کامپوننت `AgentGraphProgress` و نمایش سقف ۱۸٪ سفارش (`900,000 TMN`) و ذخیره نقدی ۴۰٪ روی سرمایه ۵ میلیون تومانی.
- **دقیقه ۱:۰۰ تا ۲:۱۵ (اثبات Backtesting و Shadow Testing)**: نمایش متریک‌های `evaluation_results/backtest_report.json` و اجرای زنده حالت `SHADOW` همراه با رندر خودکار `TradeDecisionCard`.
- **دقیقه ۲:۱۵ تا ۳:۴۵ (تایید فرم HITL، ورود به Live و آکاردئون لاگ تصمیم)**: تایید انتقال از Shadow به Live در کامپوننت `HITLApprovalModal` و باز کردن آکاردئون دلایل فارسی تصمیمات (`ai_reasoning_fa`) و پیش‌بینی مدل **Kronos** و **System-1**.
- **دقیقه ۳:۴۵ تا ۵:۰۰ (Declarative UI و تسویه ۱۰۰٪ به تومان)**: پرسیدن سوال تحلیلی در پنل چت برای رندر داینامیک `DynamicRegimeView` و نمایش اجرای ماژول تسویه اجباری پایان دوره به تومان (`100% Realized PnL in TMN`).
