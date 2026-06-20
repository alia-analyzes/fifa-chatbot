import streamlit as st
import pandas as pd

# ============================================
# PAGE CONFIG
# ============================================
st.set_page_config(
    page_title="FIFA World Cup AI Analyst",
    page_icon="⚽",
    layout="centered"
)

# ============================================
# LOAD DATA
# ============================================
@st.cache_data
def load_data():
    historical = pd.read_csv("data/historical_win.csv")
    team_stats = pd.read_csv("data/team_stats.csv")
    fixtures = pd.read_csv("data/fixtures_2026.csv")
    return historical, team_stats, fixtures

historical, team_stats, fixtures = load_data()

BIG_THREE = ["Brazil", "Argentina", "France"]
team_stats_filtered = team_stats[team_stats["team"].isin(BIG_THREE)].copy()

# Use the most recent year's row per team for "current" stats
latest_stats = team_stats_filtered.sort_values("Year").groupby("team").tail(1).set_index("team")

# ============================================
# HELPER FUNCTIONS — matched to your ACTUAL CSV columns
# ============================================
def detect_team(question):
    q = question.lower()
    for team in BIG_THREE:
        if team.lower() in q:
            return team
    return None

def get_titles(team):
    # Hardcoded from verified historical facts (CSV source data had inconsistent rows)
    known_titles = {"Brazil": 5, "Argentina": 3, "France": 2}
    return known_titles.get(team)

def get_win_rate(team):
    col = "Win Rate %"
    if col not in latest_stats.columns:
        return None
    raw = str(latest_stats.loc[team, col]).replace("%", "").strip()
    try:
        return round(float(raw), 2)
    except ValueError:
        return None

def get_goals(team):
    scored = latest_stats.loc[team].get("Total Goals Scored")
    conceded = latest_stats.loc[team].get("Sum of goals_received_last_4y")
    return scored, conceded

def get_rank(team):
    return latest_stats.loc[team].get("Rank Pre Tournemnt")

def get_squad_value(team):
    val = latest_stats.loc[team].get("Sum of squad_total_market_value_eur")
    if pd.isna(val) or val == 0:
        # fallback to the pre-computed "Squad Value (M)" measure if raw value missing
        m = latest_stats.loc[team].get("Squad Value (M)")
        return m * 1_000_000 if pd.notna(m) else None
    return val

def get_stage_progress(team):
    qf = latest_stats.loc[team].get("Sum of Real Quarterfinals")
    sf = latest_stats.loc[team].get("Sum of Real Semifinals")
    fn = latest_stats.loc[team].get("Sum of Real Finals")
    return qf, sf, fn

# --- Historical Win table helpers ---
def team_goals_column(team):
    return {"Brazil": "Brazil Goals", "Argentina": "Argentina Goals", "France": "France Goals"}[team]

def is_final_column(team):
    return {"Brazil": "Is Brazil Final", "Argentina": "Is Argentina Final", "France": "Is France Final"}[team]

def get_finals(team):
    col = is_final_column(team)
    finals = historical[historical[col] == 1].copy()
    return finals.sort_values("Year")

def get_last_win(team):
    wins = historical[historical["Champion"] == team].sort_values("Year", ascending=False)
    if len(wins) == 0:
        return None
    return int(wins.iloc[0]["Year"])

def get_topscorers(team):
    finals = get_finals(team)
    return finals[["Year", "TopScorrer"]]  # note: column is spelled "TopScorrer" in your file

def get_team_tournament_goals(team):
    finals = get_finals(team)
    col = team_goals_column(team)
    return finals[["Year", col]]

def compare_teams(metric_func, label):
    results = {team: metric_func(team) for team in BIG_THREE}
    results = {k: v for k, v in results.items() if v is not None and not pd.isna(v)}
    if not results:
        return f"I don't have data to compare {label} right now."
    best_team = max(results, key=results.get)
    lines = [f"- **{t}**: {v}" for t, v in results.items()]
    return f"Here's the comparison for {label}:\n\n" + "\n".join(lines) + f"\n\n**{best_team}** leads in this category."

# ============================================
# MAIN RESPONSE ENGINE (rule-based, no API needed)
# ============================================
def answer_question(question):
    q = question.lower()
    team = detect_team(question)

    # --- Titles / championships ---
    if any(word in q for word in ["title", "championship", "won the world cup", "world cups has"]):
        if team:
            titles = get_titles(team)
            last_win = get_last_win(team)
            return f"**{team}** has won the World Cup **{titles} times**, most recently in **{last_win}**."
        else:
            return compare_teams(get_titles, "World Cup titles")

    # --- Win rate ---
    if "win rate" in q or "win percentage" in q:
        if team:
            wr = get_win_rate(team)
            return f"**{team}**'s win rate (last 4 years) is **{wr}%**."
        else:
            return compare_teams(get_win_rate, "win rate")

    # --- Goals ---
    if "goal" in q and team:
        scored, conceded = get_goals(team)
        if pd.notna(scored) and pd.notna(conceded):
            return f"In the last 4 years, **{team}** scored **{int(scored)} goals** and conceded **{int(conceded)}**, a goal difference of **{int(scored - conceded):+d}**."
        return f"I don't have complete recent goals data for {team}."

    # --- FIFA Rank ---
    if "rank" in q:
        if team:
            rank = get_rank(team)
            return f"**{team}**'s FIFA pre-tournament ranking is **{rank}**."
        else:
            return compare_teams(get_rank, "FIFA ranking")

    # --- Finals reached ---
    if "final" in q and ("reach" in q or "how many" in q or "appear" in q):
        if team:
            finals = get_finals(team)
            years = ", ".join(str(int(y)) for y in finals["Year"])
            return f"**{team}** has reached **{len(finals)} World Cup finals**: {years}."
        else:
            return "Please mention a team — Brazil, Argentina, or France — and I'll tell you their finals record."

    # --- Top scorer / golden boot ---
    if "top scorer" in q or "golden boot" in q or "top scoring" in q:
        if team:
            scorers = get_topscorers(team)
            lines = [f"- {int(r['Year'])}: {r['TopScorrer']}" for _, r in scorers.iterrows()]
            return f"Top scorers in tournaments where **{team}** reached the final:\n\n" + "\n".join(lines)
        else:
            return "Please mention a team and I'll show you the top scorers from their final-reaching tournaments."

    # --- Tournament stage progress ---
    if "quarterfinal" in q or "semifinal" in q or "stage" in q:
        if team:
            qf, sf, fn = get_stage_progress(team)
            return f"**{team}**'s all-time stage progression: Quarterfinals **{int(qf)}**, Semifinals **{int(sf)}**, Finals **{int(fn)}**."
        else:
            return "Please mention a team and I'll show their tournament stage progression."

    # --- Team's own goals in their finals ---
    if "scored in" in q or ("goals" in q and "final" in q):
        if team:
            goals = get_team_tournament_goals(team)
            col = team_goals_column(team)
            lines = [f"- {int(r['Year'])}: {int(r[col])} goals" for _, r in goals.iterrows() if pd.notna(r[col])]
            return f"**{team}**'s goals scored in their final-reaching tournaments:\n\n" + "\n".join(lines)

    # --- Last won / most recent title ---
    if "last win" in q or ("when did" in q and "win" in q):
        if team:
            last_win = get_last_win(team)
            return f"**{team}** last won the World Cup in **{last_win}**."

    # --- Squad value ---
    if "squad value" in q or "market value" in q:
        if team:
            value = get_squad_value(team)
            if value:
                return f"**{team}**'s squad market value is approximately **€{value/1_000_000:.1f}M**."
            return f"I don't have squad value data for {team}."
        else:
            return compare_teams(lambda t: round(get_squad_value(t) / 1_000_000, 1) if get_squad_value(t) else None, "squad market value (€M)")

    # --- 2026 fixtures ---
    if "2026" in q or "fixture" in q or "next match" in q or "upcoming" in q:
        if team:
            mask = fixtures["Team1"] == team
            if "Team2" in fixtures.columns:
                mask = mask | (fixtures["Team2"] == team)
            matches = fixtures[mask]
            if len(matches) == 0:
                return f"I don't have 2026 fixture data for {team} yet."
            lines = [f"- {r.get('Stage', '')} on {r.get('Month','')} {r.get('Day','')} at {r.get('Stadium', '')}" for _, r in matches.iterrows()]
            return f"**{team}**'s upcoming 2026 World Cup fixtures:\n\n" + "\n".join(lines)
        else:
            return "Please mention a team — Brazil, Argentina, or France — and I'll show their 2026 fixtures."

    # --- Best team overall ---
    if "best team" in q or "strongest team" in q or "favourite" in q or "favorite" in q:
        return compare_teams(get_win_rate, "overall win rate") + "\n\nKeep in mind 'best' depends on the metric — ask about titles, goals, or FIFA rank for other angles!"

    # --- General comparison ---
    if "compare" in q or " vs " in q or "versus" in q:
        return compare_teams(get_titles, "World Cup titles") + "\n\n" + compare_teams(get_win_rate, "win rate")

    # --- Fallback ---
    return (
        "I'm not sure how to answer that one yet! Try asking about:\n\n"
        "- World Cup titles (e.g. *'How many titles has Brazil won?'*)\n"
        "- Win rate (e.g. *'What is Argentina's win rate?'*)\n"
        "- Goals (e.g. *'How many goals has France scored?'*)\n"
        "- Finals reached, top scorers, FIFA rank, squad value, stage progression, or 2026 fixtures\n\n"
        "Mention a team name (Brazil, Argentina, or France) for the most accurate answer!"
    )

# ============================================
# SIDEBAR
# ============================================
st.sidebar.title("⚽ GoalMind")
st.sidebar.success("100% Free — No API key needed!")
st.sidebar.markdown("### Sample Questions")
st.sidebar.markdown("""
- How many titles has Brazil won?
- What is Argentina's win rate?
- How many goals has France scored?
- Compare the three teams
- Who is the top scorer in Brazil's finals?
- What is Argentina's FIFA rank?
- Show France's 2026 fixtures
- What is Brazil's stage progression?
""")

# ============================================
# MAIN CHAT INTERFACE
# ============================================
st.title("⚽ GoalMind — FIFA World Cup AI Analyst")
st.caption("Ask me about Brazil, Argentina, and France's World Cup history & 2026 outlook")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi! I'm GoalMind 👋 Ask me anything about Brazil, Argentina, or France's World Cup history!"}
    ]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_question = st.chat_input("Ask about Brazil, Argentina, or France...")

if user_question:
    st.session_state.messages.append({"role": "user", "content": user_question})
    with st.chat_message("user"):
        st.markdown(user_question)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing the data..."):
            answer = answer_question(user_question)
            st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})
