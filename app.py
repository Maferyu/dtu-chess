import streamlit as st
import pandas as pd
import math
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import uuid

# --- ELO LOGIC ---
def calculate_elo(r_white, r_black, score_white):
    e_white = 1 / (1 + math.pow(10, (r_black - r_white) / 400))
    e_black = 1 / (1 + math.pow(10, (r_white - r_black) / 400))
    
    k = 32 # Maximum point swing
    
    new_r_white = r_white + k * (score_white - e_white)
    new_r_black = r_black + k * ((1 - score_white) - e_black)
    
    return round(new_r_white, 1), round(new_r_black, 1)

# --- UI & DATABASE SETUP ---
st.set_page_config(page_title="DTU Chess Club", page_icon="♟️")

# Custom CSS for Professional UI
st.markdown("""
    <style>
    /* Increase sidebar spacing */
    div[role="radiogroup"] > label {
        margin-bottom: 15px !important;
        font-size: 1.1rem !important;
    }
    
    /* Style the tabs to look more like buttons */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        border-radius: 4px 4px 0px 0px;
    }
    
    /* HIDE THE ANNOYING HOVER ANCHOR LINKS */
    a.header-anchor {
        display: none !important;
    }
    .st-emotion-cache-11rso9w a {
        display: none !important;
    }
    </style>
""", unsafe_allow_html=True)

# Custom Header with multiple larger pieces
st.markdown("""
    <div style="display: flex; justify-content: center; align-items: center; margin-bottom: 5px;">
        <img src="https://upload.wikimedia.org/wikipedia/commons/e/ef/Chess_ndt45.svg" width="80" style="margin-right: 15px; filter: drop-shadow(0px 0px 3px rgba(150,150,150,0.5));">
        
        <h1 style="margin: 0; padding: 0; font-family: 'Georgia', serif; font-size: 3.2rem; color: inherit;">DTU Chess Club</h1>
        
        <img src="https://upload.wikimedia.org/wikipedia/commons/c/c7/Chess_pdt45.svg" width="65" style="margin-left: 15px; filter: drop-shadow(0px 0px 3px rgba(150,150,150,0.5));">
    </div>
    <div style="width: 100%; height: 2px; background-color: #990000; margin-bottom: 35px;"></div>
""", unsafe_allow_html=True)

# Connect to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Read data with a 10-minute cache to prevent API limits
players_df = conn.read(worksheet="players", ttl="10m").dropna(how="all")
matches_df = conn.read(worksheet="matches", ttl="10m").dropna(how="all")
posts_df = conn.read(worksheet="posts", ttl="10m").dropna(how="all")

# Sidebar Navigation
page = st.sidebar.radio("Navigation", [
    "Leaderboard", 
    "Tournament Standings", 
    "Log a Match", 
    "Community Board",
    "Add New Player", 
    "Manage Data"
])

# Refresh Data Button
st.sidebar.markdown("---")
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# --- PAGE 1: LEADERBOARD ---
if page == "Leaderboard":
    
    # Time Control Filter
    col1, col2 = st.columns([2, 1])
    with col1:
        st.header("Club Standings")
    with col2:
        tc_filter = st.selectbox("Category", ["All Matches (Global ELO)", "Blitz", "Rapid", "Bullet", "Classical", "Untimed/Other"])
    
    if players_df.empty:
        st.info("No players yet! Add some players to get started.")
    else:
        if tc_filter == "All Matches (Global ELO)":
            leaderboard = players_df.sort_values(by="ELO", ascending=False).reset_index(drop=True)
            leaderboard.index = leaderboard.index + 1
            leaderboard = leaderboard[['Name', 'ELO', 'Matches']]
            st.dataframe(leaderboard.style.format({'ELO': '{:.1f}', 'Matches': '{:.0f}'}), width="stretch")
        else:
            # Dynamic ELO Calculation for specific Time Controls!
            dynamic_elos = {name: 1200.0 for name in players_df['Name']}
            dynamic_matches = {name: 0 for name in players_df['Name']}
            
            if not matches_df.empty and "Time Control" in matches_df.columns:
                filtered_matches = matches_df[matches_df["Time Control"] == tc_filter]
                
                for idx, row in filtered_matches.iterrows():
                    w = row["White"]
                    b = row["Black"]
                    res = row["Result"]
                    
                    if w not in dynamic_elos: dynamic_elos[w] = 1200.0; dynamic_matches[w] = 0
                    if b not in dynamic_elos: dynamic_elos[b] = 1200.0; dynamic_matches[b] = 0
                        
                    score = 1 if "White Wins" in res else (0.5 if "Draw" in res else 0)
                    new_w, new_b = calculate_elo(dynamic_elos[w], dynamic_elos[b], score)
                    
                    dynamic_elos[w] = new_w
                    dynamic_matches[w] += 1
                    dynamic_elos[b] = new_b
                    dynamic_matches[b] += 1
            
            dyn_df = pd.DataFrame({
                "Name": list(dynamic_elos.keys()),
                "ELO": list(dynamic_elos.values()),
                "Matches": list(dynamic_matches.values())
            })
            
            # Only show players who have actually played this time control
            dyn_df = dyn_df[dyn_df["Matches"] > 0]
            
            if dyn_df.empty:
                st.info(f"No {tc_filter} matches have been logged yet.")
            else:
                dyn_df = dyn_df.sort_values(by="ELO", ascending=False).reset_index(drop=True)
                dyn_df.index = dyn_df.index + 1
                st.dataframe(dyn_df.style.format({'ELO': '{:.1f}', 'Matches': '{:.0f}'}), width="stretch")

    st.subheader("Recent Matches")
    if not matches_df.empty:
        recent_matches = matches_df.copy()
        
        # Filter the recent matches table too!
        if tc_filter != "All Matches (Global ELO)" and "Time Control" in matches_df.columns:
            recent_matches = recent_matches[recent_matches["Time Control"] == tc_filter]
            
        if recent_matches.empty:
            st.info(f"No {tc_filter} matches played yet.")
        else:
            recent_matches.index = recent_matches.index + 1
            st.dataframe(recent_matches.iloc[::-1].head(5), width="stretch")
    else:
        st.info("No matches played yet.")

# --- PAGE 2: TOURNAMENT STANDINGS ---
elif page == "Tournament Standings":
    st.header("Spring Round Robin")
    
    st.markdown("""
    **Rules:**
    | Result | Points |
    | :--- | :--- |
    | **Win** | 3 |
    | **Draw** | 1 |
    | **Loss** | 0 |
    """)
    st.markdown("---")
    
    tab_standings, tab_schedule = st.tabs(["📊 Standings", "📅 Weekly Matchups (Simulator)"])
    
    with tab_standings:
        if matches_df.empty or "Event" not in matches_df.columns:
            st.info("No tournament matches recorded yet.")
        else:
            tourney_matches = matches_df[matches_df["Event"] == "Spring Round Robin"]
            
            if tourney_matches.empty:
                st.info("The Spring Round Robin hasn't started yet! Log a match under this event to see standings.")
            else:
                points = {}
                played = {}
                
                for idx, row in tourney_matches.iterrows():
                    w = row["White"]
                    b = row["Black"]
                    res = row["Result"]
                    
                    if w not in points: points[w] = 0; played[w] = 0
                    if b not in points: points[b] = 0; played[b] = 0
                    
                    played[w] += 1
                    played[b] += 1
                    
                    if "1-0" in res:     points[w] += 3
                    elif "0-1" in res:   points[b] += 3
                    else:                points[w] += 1; points[b] += 1
                        
                tourney_df = pd.DataFrame({
                    "Player": list(points.keys()),
                    "Points": list(points.values()),
                    "Matches Played": [played[p] for p in points.keys()]
                })
                
                tourney_df = tourney_df.sort_values(by=["Points", "Matches Played"], ascending=[False, True]).reset_index(drop=True)
                tourney_df.index = tourney_df.index + 1
                
                st.dataframe(tourney_df, width="stretch")

    with tab_schedule:
        st.write("Theoretical matchups based on currently registered players.")
        players = players_df['Name'].tolist()
        
        if len(players) < 2:
            st.warning("Not enough players to generate a schedule.")
        else:
            if len(players) % 2 != 0:
                players.append("- BYE (Rest Week) -")
                
            n = len(players)
            return_players = list(players)
            
            for fixture in range(1, n):
                st.subheader(f"Week {fixture}")
                for i in range(n // 2):
                    p1 = return_players[i]
                    p2 = return_players[n - 1 - i]
                    st.markdown(f"♟️ **{p1}** vs **{p2}**")
                
                return_players.insert(1, return_players.pop())
                st.divider()

# --- PAGE 3: LOG A MATCH ---
elif page == "Log a Match":
    st.header("Record a Result")
    
    if len(players_df) < 2:
        st.warning("You need at least 2 players in the database to log a match.")
    else:
        player_names = players_df['Name'].tolist()
        
        match_date = st.date_input("Date of the Match", datetime.now())
        
        col1, col2 = st.columns(2)
        with col1:
            white = st.selectbox("White Player", player_names)
        with col2:
            black = st.selectbox("Black Player", player_names, index=1 if len(player_names) > 1 else 0)
        
        if white == black:
            st.error("A player cannot play against themselves!")
        else:
            result = st.radio("Result", ["White Wins (1-0)", "Draw (0.5-0.5)", "Black Wins (0-1)"])
            
            col3, col4 = st.columns(2)
            with col3:
                event = st.selectbox("Event", ["Casual", "Spring Round Robin"])
            with col4:
                time_control = st.selectbox("Time Control", ["Blitz", "Rapid", "Bullet", "Classical", "Untimed/Other"])
            
            if st.button("Submit Result"):
                w_idx = players_df.index[players_df['Name'] == white].tolist()[0]
                b_idx = players_df.index[players_df['Name'] == black].tolist()[0]
                
                w_elo = float(str(players_df.at[w_idx, 'ELO']).replace(',', '.'))
                b_elo = float(str(players_df.at[b_idx, 'ELO']).replace(',', '.'))
                
                score = 1 if "White Wins" in result else (0.5 if "Draw" in result else 0)
                new_w_elo, new_b_elo = calculate_elo(w_elo, b_elo, score)
                
                players_df.at[w_idx, 'ELO'] = new_w_elo
                players_df.at[w_idx, 'Matches'] = int(players_df.at[w_idx, 'Matches']) + 1
                
                players_df.at[b_idx, 'ELO'] = new_b_elo
                players_df.at[b_idx, 'Matches'] = int(players_df.at[b_idx, 'Matches']) + 1
                
                new_match = pd.DataFrame([{
                    "Date": match_date.strftime("%Y-%m-%d"),
                    "White": white, 
                    "Black": black, 
                    "Result": result,
                    "Event": event,
                    "Time Control": time_control
                }])
                updated_matches = pd.concat([matches_df, new_match], ignore_index=True)
                
                conn.update(worksheet="players", data=players_df)
                conn.update(worksheet="matches", data=updated_matches)
                
                st.cache_data.clear()
                st.success(f"Match logged! {white} is now {new_w_elo} and {black} is now {new_b_elo}.")

# --- PAGE 4: COMMUNITY BOARD ---
elif page == "Community Board":
    st.header("💬 Community Board")
    st.write("Post club updates, challenge people, or talk trash (respectfully).")
    
    # Create new post
    with st.expander("📝 Write a new post"):
        if players_df.empty:
            st.warning("Add players to the database first!")
        else:
            author = st.selectbox("Who are you?", players_df['Name'].tolist())
            content = st.text_area("What's on your mind?")
            if st.button("Post Message"):
                if content:
                    new_id = str(uuid.uuid4())[:8] # Generate a short random ID
                    new_post = pd.DataFrame([{
                        "ID": new_id, 
                        "Author": author, 
                        "Content": content, 
                        "Likes": 0, 
                        "Dislikes": 0, 
                        "Date": datetime.now().strftime("%Y-%m-%d %H:%M")
                    }])
                    
                    if posts_df.empty:
                        updated_posts = new_post
                    else:
                        updated_posts = pd.concat([posts_df, new_post], ignore_index=True)
                        
                    conn.update(worksheet="posts", data=updated_posts)
                    st.cache_data.clear()
                    st.success("Posted!")
                    st.rerun()

    st.markdown("---")
    
    # Display posts
    if posts_df.empty:
        st.info("No posts yet. Be the first to say hi!")
    else:
        # Loop through posts in reverse chronological order
        for idx, row in posts_df.iloc[::-1].iterrows():
            with st.container(border=True):
                st.markdown(f"**{row['Author']}** • *{row['Date']}*")
                st.write(row['Content'])
                
                col1, col2, col3 = st.columns([1, 1, 8])
                
                if col1.button(f"👍 {int(row.get('Likes', 0))}", key=f"like_{row['ID']}"):
                    posts_df.at[idx, 'Likes'] = int(posts_df.at[idx, 'Likes']) + 1
                    conn.update(worksheet="posts", data=posts_df)
                    st.cache_data.clear()
                    st.rerun()
                    
                if col2.button(f"👎 {int(row.get('Dislikes', 0))}", key=f"dislike_{row['ID']}"):
                    posts_df.at[idx, 'Dislikes'] = int(posts_df.at[idx, 'Dislikes']) + 1
                    conn.update(worksheet="posts", data=posts_df)
                    st.cache_data.clear()
                    st.rerun()

# --- PAGE 5: ADD PLAYER ---
elif page == "Add New Player":
    st.header("Register New Player")
    new_name = st.text_input("Player Name")
    starting_elo = st.number_input("Starting ELO", value=1200)
    
    if st.button("Add Player"):
        if new_name in players_df['Name'].values:
            st.error("Player already exists!")
        elif new_name:
            new_player = pd.DataFrame([{
                "Name": new_name, 
                "ELO": starting_elo, 
                "Matches": 0, 
                "Creation Date": datetime.now().strftime("%Y-%m-%d")
            }])
            
            updated_players = pd.concat([players_df, new_player], ignore_index=True)
            conn.update(worksheet="players", data=updated_players)
            
            st.cache_data.clear()
            st.success(f"Added {new_name} to the club with {starting_elo} ELO!")

# --- PAGE 6: MANAGE DATA ---
elif page == "Manage Data":
    st.header("🛠️ Manage Data")
    st.write("Fix typos or delete mistakes here.")
    
    password = st.text_input("Club Password to unlock features", type="password")
    
    if password == "dtu2026":
        st.markdown("---")
        st.subheader("1. Rename a Player")
        player_to_rename = st.selectbox("Select Player", players_df['Name'].tolist(), key="rename_select")
        new_name = st.text_input("Type Correct Name")
        
        if st.button("Rename Player"):
            if new_name and new_name not in players_df['Name'].values:
                players_df.loc[players_df['Name'] == player_to_rename, 'Name'] = new_name
                
                if not matches_df.empty:
                    matches_df.loc[matches_df['White'] == player_to_rename, 'White'] = new_name
                    matches_df.loc[matches_df['Black'] == player_to_rename, 'Black'] = new_name
                
                if not posts_df.empty:
                    posts_df.loc[posts_df['Author'] == player_to_rename, 'Author'] = new_name
                
                conn.update(worksheet="players", data=players_df)
                conn.update(worksheet="matches", data=matches_df)
                if not posts_df.empty: conn.update(worksheet="posts", data=posts_df)
                
                st.cache_data.clear()
                st.success(f"Successfully renamed to {new_name}!")
                st.rerun()
            elif new_name in players_df['Name'].values:
                st.error("That name already exists!")
                
        st.markdown("---")
        st.subheader("2. Delete a Player")
        player_to_delete = st.selectbox("Select Player", players_df['Name'].tolist(), key="delete_select")
        
        if st.button("Delete Player"):
            players_df = players_df[players_df['Name'] != player_to_delete]
            conn.update(worksheet="players", data=players_df)
            st.cache_data.clear()
            st.success(f"Deleted {player_to_delete}!")
            st.rerun()

        st.markdown("---")
        st.subheader("3. Delete a Match Record")
        if not matches_df.empty:
            match_display = matches_df.apply(lambda row: f"Match {row.name + 1}: {row['White']} vs {row['Black']} ({row.get('Event', 'N/A')})", axis=1).tolist()
            match_to_delete_idx = st.selectbox("Select Match to Delete", range(len(match_display)), format_func=lambda x: match_display[x])
            
            st.warning("⚠️ Deleting a match removes it from the history table, but it DOES NOT reverse the ELO. You must fix their ELO manually in the Google Sheet.")
            
            if st.button("Delete Match"):
                matches_df = matches_df.drop(matches_df.index[match_to_delete_idx])
                conn.update(worksheet="matches", data=matches_df)
                st.cache_data.clear()
                st.success("Match deleted!")
                st.rerun()
        else:
            st.info("No matches to delete.")
