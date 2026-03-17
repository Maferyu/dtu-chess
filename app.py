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
st.set_page_config(page_title="DTU Chess Club", page_icon="DTU", layout="wide")

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
    </style>
""", unsafe_allow_html=True)

# Custom Header (Using <div> instead of <h1> completely prevents hover links!)
st.markdown(
    '<div style="display: flex; justify-content: center; align-items: center; margin-bottom: 5px;">'
    '<img src="https://upload.wikimedia.org/wikipedia/commons/f/ff/Chess_rdt45.svg" width="80" style="margin-right: 15px; filter: drop-shadow(0px 0px 3px rgba(150,150,150,0.5));">'
    '<div style="margin: 0; padding: 0; font-family: \'Georgia\', serif; font-size: 3.2rem; font-weight: bold; color: #1e1e1e;">DTU Chess Club</div>'
    '<img src="https://upload.wikimedia.org/wikipedia/commons/f/ff/Chess_rdt45.svg" width="65" style="margin-left: 15px; filter: drop-shadow(0px 0px 3px rgba(150,150,150,0.5));">'
    '</div>'
    '<div style="width: 100%; height: 2px; background-color: #990000; margin-bottom: 35px;"></div>',
    unsafe_allow_html=True
)

# Connect to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Read data with a 10-minute cache to prevent API limits
players_df = conn.read(worksheet="players", ttl="10m").dropna(how="all")
matches_df = conn.read(worksheet="matches", ttl="10m").dropna(how="all")
posts_df = conn.read(worksheet="posts", ttl="10m").dropna(how="all")

# Load dynamic events list
try:
    events_df = conn.read(worksheet="events", ttl="10m").dropna(how="all")
    events_list = events_df['Event Name'].tolist()
except Exception:
    # Fallback just in case the Google Sheet tab hasn't been created yet
    events_df = pd.DataFrame(columns=["Event Name"])
    events_list = ["Casual", "Spring Round Robin"]

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
if st.sidebar.button("Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# --- PAGE 1: LEADERBOARD ---
if page == "Leaderboard":
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown("<h2 style='padding-top: 0px;'>Club Standings</h2>", unsafe_allow_html=True)
    with col2:
        tc_filter = st.selectbox("Time Control", ["All Matches", "Blitz", "Rapid", "Bullet", "Classical", "Untimed/Other"])
    with col3:
        # Dynamically create the list of players for the filter
        player_list = ["All Players"]
        if not players_df.empty:
            player_list += sorted(players_df['Name'].tolist())
        player_filter = st.selectbox("Player", player_list)
    
    if players_df.empty:
        st.info("No players yet! Add some players to get started.")
    else:
        # General ELO for everyone
        leaderboard = players_df.sort_values(by="ELO", ascending=False).reset_index(drop=True)
        leaderboard.index = leaderboard.index + 1
        leaderboard = leaderboard[['Name', 'ELO']]
        
        st.dataframe(
            leaderboard.style.format({'ELO': '{:.1f}'}), 
            use_container_width=True
        )
        
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<h2 style='padding-top: 0px;'>Recent Matches</h2>", unsafe_allow_html=True)
        
    if not matches_df.empty:
        recent_matches = matches_df.copy()
        
        # 1. Apply Time Control Filter
        if tc_filter != "All Matches" and "Time Control" in matches_df.columns:
            recent_matches = recent_matches[recent_matches["Time Control"] == tc_filter]
            
        # 2. Apply Player Filter
        if player_filter != "All Players":
            recent_matches = recent_matches[(recent_matches["White"] == player_filter) | (recent_matches["Black"] == player_filter)]
            
        if recent_matches.empty:
            st.info("No matches found with these filters.")
        else:
            recent_matches.index = recent_matches.index + 1
            
            # Configure dataframe to display PGN nicely if it exists
            column_config = {}
            if "PGN" in recent_matches.columns:
                column_config["PGN"] = st.column_config.TextColumn("Saved Game (PGN)", width="large")
                
            st.dataframe(recent_matches.iloc[::-1].head(10), use_container_width=True, column_config=column_config)
    else:
        st.info("No matches played yet.")

# --- PAGE 2: TOURNAMENT STANDINGS ---
elif page == "Tournament Standings":
    st.markdown("<h2>Tournament Standings</h2>", unsafe_allow_html=True)
    
    # Filter out Casual games so we only show real tournaments
    tourney_options = [e for e in events_list if e != "Casual"]
    
    if not tourney_options:
        st.info("No tournaments have been created yet. Go to 'Manage Data' to add one!")
    else:
        selected_tourney = st.selectbox("Select Event", tourney_options)
        
        st.markdown("""
        **Rules:**
        | Result | Points |
        | :--- | :--- |
        | **Win** | 3 |
        | **Draw** | 1 |
        | **Loss** | 0 |
        """)
        st.markdown("---")
        
        tab_standings, tab_schedule = st.tabs(["Standings", "Weekly Matchups"])
        
        with tab_standings:
            if matches_df.empty or "Event" not in matches_df.columns:
                st.info("No matches recorded yet.")
            else:
                tourney_matches = matches_df[matches_df["Event"] == selected_tourney]
                
                if tourney_matches.empty:
                    st.info(f"No matches have been logged for {selected_tourney} yet.")
                else:
                    points = {}
                    played = {}
                    
                    for idx, row in tourney_matches.iterrows():
                        w = row.get("White", row.get("Player 1"))
                        b = row.get("Black", row.get("Player 2"))
                        res = row["Result"]
                        
                        if w not in points: points[w] = 0; played[w] = 0
                        if b not in points: points[b] = 0; played[b] = 0
                        
                        played[w] += 1
                        played[b] += 1
                        
                        if f"{w} Wins" in res or "1-0" in res or "White Wins" in res:
                            points[w] += 3
                        elif f"{b} Wins" in res or "0-1" in res or "Black Wins" in res:
                            points[b] += 3
                        else:
                            points[w] += 1; points[b] += 1
                            
                    tourney_df = pd.DataFrame({
                        "Player": list(points.keys()),
                        "Points": list(points.values()),
                        "Games Played": [played[p] for p in points.keys()]
                    })
                    
                    tourney_df = tourney_df.sort_values(by=["Points", "Games Played"], ascending=[False, True]).reset_index(drop=True)
                    tourney_df.index = tourney_df.index + 1
                    
                    st.dataframe(tourney_df, use_container_width=True)

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
                    st.markdown(f"<h3>Week {fixture}</h3>", unsafe_allow_html=True)
                    for i in range(n // 2):
                        p1 = return_players[i]
                        p2 = return_players[n - 1 - i]
                        st.markdown(f"**{p1}** vs **{p2}**")
                    
                    return_players.insert(1, return_players.pop())
                    st.divider()

# --- PAGE 3: LOG A MATCH ---
elif page == "Log a Match":
    st.markdown("<h2>Record a Result</h2>", unsafe_allow_html=True)
    
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
            result = st.radio("Result", [f"{white} Wins", "Draw", f"{black} Wins"])
            
            col3, col4 = st.columns(2)
            with col3:
                # Dynamically loads events from the database
                event = st.selectbox("Event", events_list)
            with col4:
                time_control = st.selectbox("Time Control", ["Blitz", "Rapid", "Bullet", "Classical", "Untimed/Other"])
                
            pgn_input = st.text_area("Save Game (Optional PGN)", placeholder="[Site \"Chess.com\"]\n[Result \"*\"]\n1. e4 e6 2. d4 d5...", height=100)
            
            if st.button("Submit Result"):
                w_idx = players_df.index[players_df['Name'] == white].tolist()[0]
                b_idx = players_df.index[players_df['Name'] == black].tolist()[0]
                
                w_elo = float(str(players_df.at[w_idx, 'ELO']).replace(',', '.'))
                b_elo = float(str(players_df.at[b_idx, 'ELO']).replace(',', '.'))
                
                score = 1 if result == f"{white} Wins" else (0.5 if result == "Draw" else 0)
                new_w_elo, new_b_elo = calculate_elo(w_elo, b_elo, score)
                
                players_df.at[w_idx, 'ELO'] = new_w_elo
                players_df.at[b_idx, 'ELO'] = new_b_elo
                
                db_result = f"{white} Wins" if score == 1 else ("Draw" if score == 0.5 else f"{black} Wins")
                
                new_match = pd.DataFrame([{
                    "Date": match_date.strftime("%Y-%m-%d"),
                    "White": white, 
                    "Black": black, 
                    "Result": db_result,
                    "Event": event,
                    "Time Control": time_control,
                    "PGN": pgn_input.strip() if pgn_input else "None"
                }])
                updated_matches = pd.concat([matches_df, new_match], ignore_index=True)
                
                conn.update(worksheet="players", data=players_df)
                conn.update(worksheet="matches", data=updated_matches)
                
                st.cache_data.clear()
                st.success(f"Match logged! {white} is now {new_w_elo} and {black} is now {new_b_elo}.")

# --- PAGE 4: COMMUNITY BOARD ---
elif page == "Community Board":
    st.markdown("<h2>Community Board</h2>", unsafe_allow_html=True)
    st.write("Post club updates, challenge people, or talk trash (respectfully).")
    
    with st.expander("Write a new post"):
        if players_df.empty:
            st.warning("Add players to the database first!")
        else:
            author = st.selectbox("Who are you?", players_df['Name'].tolist())
            content = st.text_area("What's on your mind?")
            if st.button("Post Message"):
                if content:
                    new_id = str(uuid.uuid4())[:8] 
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
    
    if posts_df.empty:
        st.info("No posts yet. Be the first to say hi!")
    else:
        for idx, row in posts_df.iloc[::-1].iterrows():
            with st.container(border=True):
                st.markdown(f"**{row['Author']}** • *{row['Date']}*")
                st.write(row['Content'])
                
                col1, col2, col3 = st.columns([1, 1, 8])
                
                if col1.button(f"Upvote ({int(row.get('Likes', 0))})", key=f"like_{row['ID']}"):
                    posts_df.at[idx, 'Likes'] = int(posts_df.at[idx, 'Likes']) + 1
                    conn.update(worksheet="posts", data=posts_df)
                    st.cache_data.clear()
                    st.rerun()
                    
                if col2.button(f"Downvote ({int(row.get('Dislikes', 0))})", key=f"dislike_{row['ID']}"):
                    posts_df.at[idx, 'Dislikes'] = int(posts_df.at[idx, 'Dislikes']) + 1
                    conn.update(worksheet="posts", data=posts_df)
                    st.cache_data.clear()
                    st.rerun()

# --- PAGE 5: ADD PLAYER ---
elif page == "Add New Player":
    st.markdown("<h2>Register New Player</h2>", unsafe_allow_html=True)
    new_name = st.text_input("Player Name")
    starting_elo = st.number_input("Starting ELO", value=1200)
    
    if st.button("Add Player"):
        if new_name in players_df['Name'].values:
            st.error("Player already exists!")
        elif new_name:
            new_player = pd.DataFrame([{
                "Name": new_name, 
                "ELO": starting_elo, 
                "Creation Date": datetime.now().strftime("%Y-%m-%d")
            }])
            
            updated_players = pd.concat([players_df, new_player], ignore_index=True)
            conn.update(worksheet="players", data=updated_players)
            
            st.cache_data.clear()
            st.success(f"Added {new_name} to the club with {starting_elo} ELO!")

# --- PAGE 6: MANAGE DATA ---
elif page == "Manage Data":
    st.markdown("<h2>Manage Data</h2>", unsafe_allow_html=True)
    st.write("Fix typos, delete mistakes, or create new events here.")
    
    password = st.text_input("Club Password to unlock features", type="password")
    
    if password == "dtu2026":
        
        st.markdown("---")
        st.markdown("<h3>1. Create a New Event</h3>", unsafe_allow_html=True)
        new_event = st.text_input("Event Name (e.g., Fall Championship 2026)")
        
        if st.button("Create Event"):
            if new_event and new_event not in events_list:
                new_event_df = pd.DataFrame([{"Event Name": new_event}])
                
                if events_df.empty:
                    updated_events = new_event_df
                else:
                    updated_events = pd.concat([events_df, new_event_df], ignore_index=True)
                    
                conn.update(worksheet="events", data=updated_events)
                st.cache_data.clear()
                st.success(f"Successfully created tournament: {new_event}!")
                st.rerun()
            elif new_event in events_list:
                st.error("That event name already exists!")
                
        st.markdown("---")
        st.markdown("<h3>2. Rename a Player</h3>", unsafe_allow_html=True)
        player_to_rename = st.selectbox("Select Player", players_df['Name'].tolist(), key="rename_select")
        new_name = st.text_input("Type Correct Name")
        
        if st.button("Rename Player"):
            if new_name and new_name not in players_df['Name'].values:
                players_df.loc[players_df['Name'] == player_to_rename, 'Name'] = new_name
                
                if not matches_df.empty:
                    if 'White' in matches_df.columns:
                        matches_df.loc[matches_df['White'] == player_to_rename, 'White'] = new_name
                        matches_df.loc[matches_df['Black'] == player_to_rename, 'Black'] = new_name
                    if 'Player 1' in matches_df.columns:
                        matches_df.loc[matches_df['Player 1'] == player_to_rename, 'Player 1'] = new_name
                        matches_df.loc[matches_df['Player 2'] == player_to_rename, 'Player 2'] = new_name
                    matches_df.loc[matches_df['Result'] == f"{player_to_rename} Wins", 'Result'] = f"{new_name} Wins"
                
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
        st.markdown("<h3>3. Delete a Player</h3>", unsafe_allow_html=True)
        player_to_delete = st.selectbox("Select Player", players_df['Name'].tolist(), key="delete_select")
        
        if st.button("Delete Player"):
            players_df = players_df[players_df['Name'] != player_to_delete]
            conn.update(worksheet="players", data=players_df)
            st.cache_data.clear()
            st.success(f"Deleted {player_to_delete}!")
            st.rerun()

        st.markdown("---")
        st.markdown("<h3>4. Delete a Match Record</h3>", unsafe_allow_html=True)
        if not matches_df.empty:
            def format_match_row(row):
                p1 = row.get('White', row.get('Player 1', 'Unknown'))
                p2 = row.get('Black', row.get('Player 2', 'Unknown'))
                return f"Match {row.name + 1}: {p1} vs {p2} ({row.get('Event', 'N/A')})"
                
            match_display = matches_df.apply(format_match_row, axis=1).tolist()
            match_to_delete_idx = st.selectbox("Select Match to Delete", range(len(match_display)), format_func=lambda x: match_display[x])
            
            st.warning("Deleting a match removes it from the history table, but it DOES NOT reverse the ELO. You must fix their ELO manually in the Google Sheet.")
            
            if st.button("Delete Match"):
                matches_df = matches_df.drop(matches_df.index[match_to_delete_idx])
                conn.update(worksheet="matches", data=matches_df)
                st.cache_data.clear()
                st.success("Match deleted!")
                st.rerun()
        else:
            st.info("No matches to delete.")
