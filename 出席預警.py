import streamlit as st
import pandas as pd
from datetime import date, timedelta

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="出席預警計算系統", page_icon="🏫", layout="wide")

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700;900&display=swap');
html,body,[class*="css"]{font-family:'Noto Sans TC',sans-serif;}
.stApp{background:#f5f0e8;}
[data-testid="stSidebar"]{background:#2c2c2c!important;}
[data-testid="stSidebar"] * { color: #f5f0e8 !important; }
[data-testid="stSidebar"] input { color: #1a1a1a !important; background: #ffffff !important; }
h1{color:#f5f0e8!important;font-weight:900!important;letter-spacing:-1px;}
h2{color:#f5f0e8!important;font-weight:700!important;}
h3{color:#f5f0e8!important;font-weight:700!important;}
.card{background:white;border-radius:16px;padding:20px;margin-bottom:14px;
      border:2px solid #e8e0d0;box-shadow:4px 4px 0 #1a1a1a;}
.card-danger {background:#fff5f5;border-color:#e53935;box-shadow:4px 4px 0 #e53935;}
.card-warning{background:#fffde7;border-color:#f9a825;box-shadow:4px 4px 0 #f9a825;}
.card-safe   {background:#f1f8e9;border-color:#558b2f;box-shadow:4px 4px 0 #558b2f;}
.card-last   {background:#fff3e0;border-color:#e65100;box-shadow:4px 4px 0 #e65100;}

.badge{display:inline-block;padding:4px 12px;border-radius:20px;font-size:13px;font-weight:700;margin-left:8px;}
.badge-danger {background:#ffcdd2;color:#b71c1c;}
.badge-warning{background:#fff9c4;color:#f57f17;}
.badge-safe   {background:#dcedc8;color:#33691e;}
.badge-last   {background:#ffe0b2;color:#bf360c;}

.stButton>button{background:#1a1a1a!important;color:#f5f0e8!important;border:none!important;
  border-radius:8px!important;font-weight:700!important;font-family:'Noto Sans TC',sans-serif!important;
  padding:10px 24px!important;box-shadow:3px 3px 0 #888!important;transition:transform .1s,box-shadow .1s!important;}
.stButton>button:hover{transform:translate(-1px,-1px)!important;box-shadow:4px 4px 0 #888!important;}

hr{border-color:#e8e0d0;}
.section-title{font-size:22px;font-weight:900;color:#1a1a1a;
  border-left:5px solid #d4a843;padding-left:12px;margin:24px 0 16px 0;}
.tag{display:inline-block;background:#d4a843;color:white;border-radius:6px;
  padding:2px 10px;font-size:12px;font-weight:700;margin-right:6px;}
.day-tag{display:inline-block;background:#5c6bc0;color:white;border-radius:6px;
  padding:2px 10px;font-size:12px;font-weight:700;margin-right:4px;}
.hero{background:#1a1a1a;color:#f5f0e8;border-radius:20px;padding:32px 40px;margin-bottom:32px;}
.alert-last{background:#fff3e0;border:2px solid #e65100;border-radius:12px;
  padding:12px 16px;margin:8px 0;font-weight:700;color:#bf360c;}
[data-testid="metric-container"]{background:white;border-radius:12px;padding:16px;border:2px solid #e8e0d0;}

/* Timetable */
.tt{width:100%;border-collapse:collapse;font-size:13px;}
.tt th{background:#1a1a1a;color:#f5f0e8;padding:10px 8px;text-align:center;font-weight:700;border:1px solid #333;}
.tt td{border:1px solid #ddd;padding:6px 4px;text-align:center;vertical-align:middle;min-width:90px;height:38px;}
.tt tr:nth-child(even) td{background:#fafafa;}
.tt td.plabel{background:#f0ebe0;font-weight:700;color:#555;font-size:12px;}
.chip{border-radius:8px;padding:4px 8px;font-weight:700;font-size:12px;white-space:nowrap;}
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "courses"    not in st.session_state: st.session_state.courses    = []
if "holidays"   not in st.session_state: st.session_state.holidays   = []
if "form_reset" not in st.session_state: st.session_state.form_reset = 0

# ── Constants ─────────────────────────────────────────────────────────────────
WEEKDAY_MAP   = {"一":0,"二":1,"三":2,"四":3,"五":4}
ALL_DAYS      = ["一","二","三","四","五"]
# Fix #2: period numbers only, no times
PERIOD_OPTIONS = ["第1節", "第2節", "第3節", "第4節", "第n節", "第5節", "第6節", "第7節", "第8節", "第9節"]
COURSE_COLORS  = [
    ("#4e79a7","#fff"),("#f28e2b","#fff"),("#e15759","#fff"),
    ("#76b7b2","#fff"),("#59a14f","#fff"),("#edc948","#333"),
    ("#b07aa1","#fff"),("#ff9da7","#333"),("#9c755f","#fff"),
    ("#bab0ac","#333"),
]

# ── Helpers ───────────────────────────────────────────────────────────────────
def period_num(p: str) -> int:
    order = {"1":1,"2":2,"3":3,"4":4,"n":5,"5":6,"6":7,"7":8,"8":9,"9":10}
    key = p.replace("第","").replace("節","").strip()
    return order.get(key, 99)

def count_school_days(start: date, end: date, weekday: int, holidays: list) -> int:
    count, d = 0, start
    while d.weekday() != weekday:
        d += timedelta(days=1)
    while d <= end:
        if d not in holidays: count += 1
        d += timedelta(days=7)
    return count

def compute_stats(c: dict, sem_start, sem_end, holidays) -> dict:
    day_sessions  = c.get("day_sessions", {})
    total_classes = 0
    periods_per_day = {}
    for day, ps in day_sessions.items():
        sd = count_school_days(sem_start, sem_end, WEEKDAY_MAP[day], holidays)
        total_classes += sd * len(ps)
        periods_per_day[day] = len(ps)

    if total_classes == 0:
        return dict(total_classes=0, limit=0, remaining=0, remaining_days=0, pct=0, status="safe")

    # Fix #4: teacher_limit overrides 1/3 default
    tl    = c.get("teacher_limit")
    limit = int(tl) if (tl is not None) else (total_classes // 3)

    remaining     = limit - c.get("absent", 0)
    pct           = c.get("absent", 0) / total_classes
    avg_p         = max(periods_per_day.values()) if periods_per_day else 1
    remaining_days = max(remaining // avg_p, 0) if avg_p else 0

    if remaining <= 0:         status = "danger"
    elif remaining_days == 1:  status = "last"
    elif remaining_days <= 2:  status = "warning"
    else:                      status = "safe"

    return dict(total_classes=total_classes, limit=limit,
                remaining=remaining, remaining_days=remaining_days,
                pct=pct, status=status)

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## ⚙️ 學期設定")
    st.markdown("---")
    sem_start = st.date_input("📅 開學日",     value=date(2025, 9, 1))
    sem_end   = st.date_input("📅 學期結束日", value=date(2026, 1, 17))
    st.markdown("---")
    st.markdown("### 🗓️ 假日清單")
    st.caption("每行一個，格式 YYYY-MM-DD")
    holiday_text = st.text_area("假日", height=120, placeholder="2025-10-10\n2025-11-01\n...")
    holidays_parsed = []
    for line in holiday_text.strip().splitlines():
        line = line.strip()
        if line:
            try:    holidays_parsed.append(date.fromisoformat(line))
            except: st.warning(f"格式錯誤：{line}")
    st.session_state.holidays = holidays_parsed
    st.markdown(f"**已設定假日：** {len(holidays_parsed)} 天")
    for h in holidays_parsed:
        st.markdown(f"- {h.strftime('%Y/%m/%d')}")

# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="hero">
  <h1 style="color:#f5f0e8;margin:0;font-size:2.2rem;">🏫 出席預警計算系統</h1>
  <p style="color:#aaa;margin:8px 0 0 0;font-size:1rem;">
    教育部規定：每科缺課不得超過學期總節數的
    <strong style="color:#d4a843;">1/3</strong>，
    剩最後一次可缺席機會時系統會主動提醒 🔔
  </p>
</div>
""", unsafe_allow_html=True)

tabs = st.tabs(["📋 課程管理", "🗓️ 完整課表", "📊 出席狀況", "💡 請假建議"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 – Course management
# ══════════════════════════════════════════════════════════════════════════════
with tabs[0]:
    st.markdown('<div class="section-title">新增課程</div>', unsafe_allow_html=True)

    r = st.session_state.form_reset   # Fix #1: all widget keys carry this suffix

    # Basic info
    col1, col2 = st.columns([3, 2])
    with col1:
        course_options = ["自行輸入…","國文","英語","數學","生物","化學","物理","地科","歷史","地理","公民","體育","美術"]
        selected_course = st.selectbox("課程名稱", options=course_options, key=f"sel_{r}")
        if selected_course == "自行輸入…":
            new_name = st.text_input("輸入課程名稱", placeholder="請輸入課程名稱", key=f"nm_{r}")
        else:
            new_name = selected_course
    with col2:
        new_absent = st.number_input("已缺席節數（累計）", min_value=0, value=0, key=f"ab_{r}")
    # Fix #4: optional custom limit
    col3, col4 = st.columns([2, 3])
    with col3:
        use_custom = st.checkbox("老師自訂缺席上限", key=f"uc_{r}")
    with col4:
        if use_custom:
            teacher_limit = st.number_input(
                "最多可缺席節數（老師規定）", min_value=0, value=10, key=f"tl_{r}"
            )
        else:
            teacher_limit = None
            st.caption("未勾選則預設使用 **總節數 ÷ 3**")

    # Fix #1 & Fix #2: day checkboxes + period multiselect (no times)
    st.markdown("**📅 上課時間設定**")
    st.caption("勾選有上課的星期，再選擇那天的第幾節（可複選）")

    day_sessions: dict[str, list[str]] = {}
    cols = st.columns(5)
    for i, day in enumerate(ALL_DAYS):
        with cols[i]:
            checked = st.checkbox(f"週{day}", key=f"d_{day}_{r}")   # key resets on submit
            if checked:
                selected = st.multiselect(
                    "節次",
                    options=PERIOD_OPTIONS,        # Fix #2: "第N節" only, no time strings
                    key=f"p_{day}_{r}",
                    placeholder="選節次…",
                    label_visibility="collapsed",
                )
                if selected:
                    day_sessions[day] = sorted(selected, key=period_num)

    if st.button("➕ 新增課程", key=f"add_{r}"):
        if not new_name.strip():
            st.error("請輸入課程名稱！")
        elif not day_sessions:
            st.error("請至少勾選一天並選擇節次！")
        else:
            st.session_state.courses.append({
                "name":          new_name.strip(),
                "days":          list(day_sessions.keys()),
                "day_sessions":  day_sessions,
                "absent":        int(new_absent),
                "teacher_limit": teacher_limit,
            })
            st.success(f"✅ 已新增《{new_name.strip()}》")
            st.session_state.form_reset += 1   # Fix #1: triggers full form reset
            st.rerun()

    # ── Existing course list ──────────────────────────────────────────────────
    st.markdown('<div class="section-title">已新增課程</div>', unsafe_allow_html=True)

    if not st.session_state.courses:
        st.info("尚未新增任何課程，請在上方填寫後按「新增課程」。")
    else:
        for i, c in enumerate(st.session_state.courses):
            stats  = compute_stats(c, sem_start, sem_end, st.session_state.holidays)
            status = stats["status"]
            card_cls  = "card-last" if status == "last" else f"card-{status}"
            badge_cls = "badge-last" if status == "last" else f"badge-{status}"
            badge_text = {"danger":"⛔ 超過上限","last":"🔔 最後一次！",
                          "warning":"⚠️ 接近上限","safe":"✅ 正常"}[status]

            schedule_lines = [
                f"週{day}：{'、'.join(ps)}（共 {len(ps)} 節）"
                for day, ps in c.get("day_sessions", {}).items()
            ]
            limit_note = (
                f"老師限制：<strong>{c['teacher_limit']}</strong> 節"
                if c.get("teacher_limit") is not None
                else f"上限 1/3：<strong>{stats['limit']}</strong> 節"
            )

            st.markdown(f"""
            <div class="card {card_cls}">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <span style="font-size:18px;font-weight:700;">{c['name']}</span>
                <span class="badge {badge_cls}">{badge_text}</span>
              </div>
              <div style="color:#555;font-size:13px;margin-top:10px;line-height:2.2;">
                {'<br>'.join(schedule_lines)}<br>
                學期總節數：<strong>{stats['total_classes']}</strong> 節　
                {limit_note}　
                已缺席：<strong>{c['absent']}</strong> 節　
                剩餘：<strong>{stats['remaining']}</strong> 節
                ＝ <strong>{stats['remaining_days']}</strong> 次
              </div>
            </div>
            """, unsafe_allow_html=True)

            if status == "last":
                st.markdown(
                    '<div class="alert-last">🔔 本科只剩最後一次可缺課機會，請三思再請假！</div>',
                    unsafe_allow_html=True
                )

            col_ab, col_lim, col_del = st.columns([3, 3, 1])

            with col_ab:
                new_ab = st.number_input(
                    f"《{c['name']}》已缺席節數",
                    min_value=0, value=c["absent"], key=f"absent_{i}"
                )
                if new_ab != c["absent"]:
                    st.session_state.courses[i]["absent"] = int(new_ab)
                    st.rerun()

            with col_lim:
                use_lim = st.checkbox(
                    "老師自訂上限",
                    value=(c.get("teacher_limit") is not None),
                    key=f"use_lim_{i}"
                )
                if use_lim:
                    cur_lim = c.get("teacher_limit") if c.get("teacher_limit") is not None else stats["limit"]
                    new_lim = st.number_input(
                        "老師規定上限（節）", min_value=0, value=int(cur_lim), key=f"lim_{i}"
                    )
                    if new_lim != c.get("teacher_limit"):
                        st.session_state.courses[i]["teacher_limit"] = int(new_lim)
                        st.rerun()
                else:
                    if c.get("teacher_limit") is not None:
                        st.session_state.courses[i]["teacher_limit"] = None
                        st.rerun()

            with col_del:
                st.markdown("<br><br>", unsafe_allow_html=True)
                if st.button("🗑️", key=f"del_{i}", use_container_width=True):
                    st.session_state.courses.pop(i)
                    st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 – Full timetable (Fix #3)
# ══════════════════════════════════════════════════════════════════════════════
with tabs[1]:
    st.markdown('<div class="section-title">🗓️ 完整課表</div>', unsafe_allow_html=True)

    if not st.session_state.courses:
        st.info("請先在「課程管理」新增課程，課表會自動生成。")
    else:
        # Collect all period numbers across all courses
        all_pnums: set[int] = set()
        for c in st.session_state.courses:
            for ps in c.get("day_sessions", {}).values():
                for p in ps:
                    all_pnums.add(period_num(p))

        if not all_pnums:
            st.info("課程尚未設定節次。")
        else:
            # Build cell lookup: (day, pnum) → course index
            cell_map: dict[tuple, int] = {}
            for idx, c in enumerate(st.session_state.courses):
                for day, ps in c.get("day_sessions", {}).items():
                    for p in ps:
                        cell_map[(day, period_num(p))] = idx

            # Render HTML table
            header_html = "".join(f"<th>週{d}</th>" for d in ALL_DAYS)
            rows_html   = ""
            for pn in range(min(all_pnums), max(all_pnums) + 1):
                row = f"<td class='plabel'>第{pn}節</td>"
                for day in ALL_DAYS:
                    idx = cell_map.get((day, pn))
                    if idx is not None:
                        c  = st.session_state.courses[idx]
                        bg, fg = COURSE_COLORS[idx % len(COURSE_COLORS)]
                        row += (
                            f"<td><span class='chip' style='background:{bg};color:{fg};'>"
                            f"{c['name']}</span></td>"
                        )
                    else:
                        row += "<td style='color:#ccc;'>—</td>"
                rows_html += f"<tr>{row}</tr>"

            st.markdown(f"""
            <div style="overflow-x:auto;margin-bottom:16px;">
            <table class="tt">
              <thead><tr><th>節次</th>{header_html}</tr></thead>
              <tbody>{rows_html}</tbody>
            </table>
            </div>
            """, unsafe_allow_html=True)

            # Legend
            st.markdown("**圖例**")
            legend = "".join(
                f"<span class='chip' style='background:{COURSE_COLORS[i % len(COURSE_COLORS)][0]};"
                f"color:{COURSE_COLORS[i % len(COURSE_COLORS)][1]};margin:4px;padding:6px 14px;'>"
                f"{c['name']}</span>"
                for i, c in enumerate(st.session_state.courses)
            )
            st.markdown(
                f"<div style='display:flex;flex-wrap:wrap;gap:4px;margin-top:8px;'>{legend}</div>",
                unsafe_allow_html=True
            )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 – Attendance overview
# ══════════════════════════════════════════════════════════════════════════════
with tabs[2]:
    st.markdown('<div class="section-title">出席狀況總覽</div>', unsafe_allow_html=True)

    if not st.session_state.courses:
        st.info("請先在「課程管理」頁面新增課程。")
    else:
        danger_count = warning_count = last_count = safe_count = 0
        rows, all_stats = [], []

        for c in st.session_state.courses:
            stats = compute_stats(c, sem_start, sem_end, st.session_state.holidays)
            all_stats.append((c, stats))
            s = stats["status"]
            if s == "danger":    danger_count += 1
            elif s == "last":    last_count   += 1
            elif s == "warning": warning_count += 1
            else:                safe_count   += 1

            rows.append({
                "課程":     c["name"],
                "上課天":   "、".join(f"週{d}" for d in c.get("days", [])),
                "總節數":   stats["total_classes"],
                "缺席上限": stats["limit"],
                "上限來源": "老師規定" if c.get("teacher_limit") is not None else "1/3規定",
                "已缺席":   c["absent"],
                "剩餘節數": stats["remaining"],
                "剩餘次數": stats["remaining_days"],
                "缺席率":   f"{stats['pct']:.0%}",
                "狀態":     {"danger":"⛔ 超標","last":"🔔 最後一次","warning":"⚠️ 注意","safe":"✅ 正常"}[s],
            })

        m1,m2,m3,m4,m5 = st.columns(5)
        m1.metric("📚 課程總數",  len(st.session_state.courses))
        m2.metric("⛔ 超標科目",  danger_count)
        m3.metric("🔔 最後一次",  last_count)
        m4.metric("⚠️ 注意科目",  warning_count)
        m5.metric("✅ 正常科目",  safe_count)

        st.markdown("---")

        for c, stats in all_stats:
            status   = stats["status"]
            color    = {"danger":"#e53935","last":"#e65100","warning":"#f9a825","safe":"#558b2f"}[status]
            card_cls = "card-last" if status == "last" else f"card-{status}"
            pct      = stats["pct"]
            limit_pct = stats["limit"] / stats["total_classes"] if stats["total_classes"] else 1/3

            st.markdown(f'<div class="card {card_cls}">', unsafe_allow_html=True)
            ci, cb = st.columns([2, 3])

            with ci:
                days_str = "、".join(f"週{d}" for d in c.get("days", []))
                st.markdown(f"**{c['name']}**　`{days_str}`")
                limit_note = (
                    f"老師限制 **{c['teacher_limit']}** 節"
                    if c.get("teacher_limit") is not None
                    else f"上限 1/3：**{stats['limit']}** 節"
                )
                st.markdown(f"缺席 **{c['absent']}** / **{stats['total_classes']}** 節　{limit_note}")
                if stats["remaining"] > 0:
                    msg = ("⚠️ 僅剩最後 1 次完整缺課機會！" if status == "last"
                           else f"還可缺席 {stats['remaining']} 節（{stats['remaining_days']} 次）")
                else:
                    msg = f"已超出上限 {abs(stats['remaining'])} 節！"
                st.markdown(f"<span style='color:{color};font-weight:700;'>{msg}</span>",
                            unsafe_allow_html=True)

            with cb:
                bar_pct = min(pct / limit_pct, 1.0) if limit_pct else 1.0
                st.markdown(f"**缺席率：{pct:.0%}**（上限 {limit_pct:.0%}）")
                st.markdown(f"""
                <div style="background:#e0e0e0;border-radius:8px;height:18px;overflow:hidden;margin-top:8px;">
                  <div style="width:{bar_pct*100:.1f}%;background:{color};height:100%;border-radius:8px;"></div>
                </div>
                <div style="display:flex;justify-content:space-between;font-size:12px;color:#666;margin-top:4px;">
                  <span>0%</span>
                  <span style="color:{color};font-weight:700;">{pct:.0%}</span>
                  <span>上限 {limit_pct:.0%}</span>
                </div>
                """, unsafe_allow_html=True)
                sched = "".join(
                    f"<span class='day-tag'>週{day}</span>{'、'.join(ps)}<br>"
                    for day, ps in c.get("day_sessions", {}).items()
                )
                st.markdown(
                    f"<div style='margin-top:10px;font-size:12px;color:#555;line-height:2;'>{sched}</div>",
                    unsafe_allow_html=True
                )
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown('<div class="section-title">完整表格</div>', unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 – Leave recommendations
# ══════════════════════════════════════════════════════════════════════════════
with tabs[3]:
    st.markdown('<div class="section-title">💡 請假建議</div>', unsafe_allow_html=True)
    st.caption("以「每次上課（整天的節次）」為單位，計算還可以缺席幾次。")

    if not st.session_state.courses:
        st.info("請先在「課程管理」頁面新增課程。")
    else:
        ranked = []
        for c in st.session_state.courses:
            stats = compute_stats(c, sem_start, sem_end, st.session_state.holidays)
            ranked.append({**c, **stats})
        ranked_sorted = sorted(ranked, key=lambda x: x["remaining_days"], reverse=True)

        # Last-chance banner
        last_list = [r for r in ranked_sorted if r["status"] == "last"]
        if last_list:
            names = "、".join(f"《{r['name']}》" for r in last_list)
            st.markdown(f"""
            <div style="background:#fff3e0;border:2px solid #e65100;border-radius:12px;
                        padding:14px 20px;margin-bottom:20px;">
              🔔 <strong style="color:#bf360c;font-size:16px;">
                最後一次缺課提醒：{names} 只剩最後一次可缺課機會！
              </strong>
            </div>
            """, unsafe_allow_html=True)

        col_ok, col_warn = st.columns(2)

        with col_ok:
            st.markdown("### ✅ 可以請假的課")
            safe_list = [r for r in ranked_sorted if r["status"] == "safe"]
            if safe_list:
                for r in safe_list:
                    days_str = "、".join(f"週{d}" for d in r.get("days", []))
                    st.markdown(f"""
                    <div class="card card-safe" style="margin-bottom:10px;">
                      <strong>{r['name']}</strong>
                      <span style="color:#558b2f;margin-left:8px;">
                        還可缺課 <strong>{r['remaining_days']}</strong> 次（{r['remaining']} 節）
                      </span><br>
                      <span style="font-size:13px;color:#666;">{days_str}｜已缺 {r['absent']} / {r['total_classes']} 節</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.warning("目前沒有寬裕的科目，請謹慎！")

        with col_warn:
            st.markdown("### ⚠️ 需要注意 / 不建議請假")
            shown = False
            for r in ranked_sorted:
                days_str = "、".join(f"週{d}" for d in r.get("days", []))
                if r["status"] == "last":
                    shown = True
                    st.markdown(f"""
                    <div class="card card-last" style="margin-bottom:10px;">
                      🔔 <strong>{r['name']}</strong>
                      <span style="color:#bf360c;margin-left:8px;">最後一次缺課機會！</span><br>
                      <span style="font-size:13px;color:#666;">{days_str}｜已缺 {r['absent']} / {r['total_classes']} 節</span>
                    </div>
                    """, unsafe_allow_html=True)
                elif r["status"] == "warning":
                    shown = True
                    st.markdown(f"""
                    <div class="card card-warning" style="margin-bottom:10px;">
                      ⚠️ <strong>{r['name']}</strong>
                      <span style="color:#f57f17;margin-left:8px;">僅剩 {r['remaining_days']} 次</span><br>
                      <span style="font-size:13px;color:#666;">{days_str}｜已缺 {r['absent']} / {r['total_classes']} 節</span>
                    </div>
                    """, unsafe_allow_html=True)
                elif r["status"] == "danger":
                    shown = True
                    st.markdown(f"""
                    <div class="card card-danger" style="margin-bottom:10px;">
                      ⛔ <strong>{r['name']}</strong>
                      <span style="color:#e53935;margin-left:8px;">已超出上限 {abs(r['remaining'])} 節！</span><br>
                      <span style="font-size:13px;color:#666;">{days_str}｜已缺 {r['absent']} / {r['total_classes']} 節</span>
                    </div>
                    """, unsafe_allow_html=True)
            if not shown:
                st.success("目前所有課程都在安全範圍內，繼續保持！")

        # Date picker
        st.markdown("---")
        st.markdown("### 📆 選擇日期查看當天請假建議")
        st.caption("選一天，系統告訴你當天每堂課的節次與建議。")

        target_date = st.date_input("選擇請假日期", value=date.today())
        wd = target_date.weekday()

        if wd >= 5:
            st.info("所選日期是週末，沒有排課。")
        else:
            day_key = ALL_DAYS[wd]
            day_courses = [r for r in ranked if day_key in r.get("days", [])]
            if not day_courses:
                st.info(f"週{day_key} 沒有排課，或你還沒新增該天的課程。")
            else:
                st.markdown(f"**{target_date.strftime('%Y/%m/%d')}（週{day_key}）的課程：**")
                for r in day_courses:
                    periods = r.get("day_sessions", {}).get(day_key, [])
                    p_str   = "、".join(periods)
                    icon, color, msg = {
                        "safe":    ("✅","#558b2f", f"可請假，剩餘 {r['remaining_days']} 次機會"),
                        "last":    ("🔔","#bf360c", "最後一次可缺課機會，請三思！"),
                        "warning": ("⚠️","#f57f17", f"謹慎，只剩 {r['remaining_days']} 次"),
                        "danger":  ("⛔","#e53935", f"不建議請假，已超標 {abs(r['remaining'])} 節"),
                    }[r["status"]]
                    st.markdown(f"""
                    <div class="card" style="margin-bottom:10px;border-color:{color};box-shadow:4px 4px 0 {color};">
                      <div style="font-size:16px;font-weight:700;">{icon} {r['name']}</div>
                      <div style="font-size:13px;color:#555;margin-top:8px;line-height:2;">
                        📚 <strong>{p_str}</strong>　共 {len(periods)} 節<br>
                        <span style="color:{color};font-weight:700;">{msg}</span>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
