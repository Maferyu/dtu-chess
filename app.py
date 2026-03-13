import streamlit as st
import pandas as pd
import math
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

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
st.title("♟️ DTU Chess Club Tracker")

# Connect to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Read data with a 10-minute cache to prevent API limits
players_df = conn.read(worksheet="players", ttl="10m").dropna(how="all")
matches_df = conn.read(worksheet="matches", ttl="10m").dropna(how="all")

# Sidebar Navigation
page = st.sidebar.radio("Navigation", [
    "Leaderboard", 
    "Tournament Standings", 
    "Log a Match", 
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
    st.header("Global Standings")
    
    if players_df.empty:
        st.info("No players yet! Add some players to get started.")
    else:
        # Sort by ELO and reset index for rank numbers
        leaderboard = players_df.sort_values(by="ELO", ascending=False).reset_index(drop=True)
        leaderboard.index = leaderboard.index + 1
        
        # Keep only the columns we want to show
        leaderboard = leaderboard[['Name', 'ELO', 'Matches']]
        
        st.dataframe(
            leaderboard.style.format({'ELO': '{:.1f}', 'Matches': '{:.0f}'}), 
            width="stretch"
        )
        
    st.subheader("Recent Matches")
    if not matches_df.empty:
        recent_matches = matches_df.copy()
        recent_matches.index = recent_matches.index + 1 # Match 1, 2, 3...
        # Flip upside down and take top 5
        st.dataframe(recent_matches.iloc[::-1].head(5), width="stretch")
    else:
        st.info("No matches played yet.")

# --- PAGE 2: TOURNAMENT STANDINGS ---
elif page == "Tournament Standings":
    st.header("Spring Round Robin")
    st.markdown("""
    **Rules:** 
    * Win = 3 Points
    * Draw = 1 Point
    * Loss = 0 Points
    """)
    
    if matches_df.empty or "Event" not in matches_df.columns:
        st.info("No tournament matches recorded yet.")
    else:
        tourney_matches = matches_df[matches_df["Event"] == "Spring Round Robin"]
        
        if tourney_matches.empty:
            st.info("The Spring Round Robin hasn't started yet! Log a match under this event to see standings.")
        else:
            # Calculate 3-1-0 points
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
                
                if "1-0" in res:     # White wins
                    points[w] += 3
                elif "0-1" in res:   # Black wins
                    points[b] += 3
                else:                # Draw
                    points[w] += 1
                    points[b] += 1
                    
            # Build Tournament DataFrame
            tourney_df = pd.DataFrame({
                "Player": list(points.keys()),
                "Points": list(points.values()),
                "Matches Played": [played[p] for p in points.keys()]
            })
            
            # Sort by highest points. Tiebreaker: fewest matches played
            tourney_df = tourney_df.sort_values(by=["Points", "Matches Played"], ascending=[False, True]).reset_index(drop=True)
            tourney_df.index = tourney_df.index + 1
            
            st.dataframe(tourney_df, width="stretch")

# --- PAGE 3: LOG A MATCH ---
elif page == "Log a Match":
    st.header("Record a Result")
    
    if len(players_df) < 2:
        st.warning("You need at least 2 players in the database to log a match.")
    else:
        player_names = players_df['Name'].tolist()
        
        white = st.selectbox("White Player", player_names)
        black = st.selectbox("Black Player", player_names, index=1 if len(player_names) > 1 else 0)
        
        if white == black:
            st.error("A player cannot play against themselves!")
        else:
            result = st.radio("Result", ["White Wins (1-0)", "Draw (0.5-0.5)", "Black Wins (0-1)"])
            event = st.selectbox("Event", ["Casual", "Spring Round Robin"])
            
            if st.button("Submit Result"):
                w_idx = players_df.index[players_df['Name'] == white].tolist()[0]
                b_idx = players_df.index[players_df['Name'] == black].tolist()[0]
                
                # Safely parse ELO, replacing European commas just in case
                w_elo = float(str(players_df.at[w_idx, 'ELO']).replace(',', '.'))
                b_elo = float(str(players_df.at[b_idx, 'ELO']).replace(',', '.'))
                
                score = 1 if "White Wins" in result else (0.5 if "Draw" in result else 0)
                new_w_elo, new_b_elo = calculate_elo(w_elo, b_elo, score)
                
                players_df.at[w_idx, 'ELO'] = new_w_elo
                players_df.at[w_idx, 'Matches'] = int(players_df.at[w_idx, 'Matches']) + 1
                
                players_df.at[b_idx, 'ELO'] = new_b_elo
                players_df.at[b_idx, 'Matches'] = int(players_df.at[b_idx, 'Matches']) + 1
                
                new_match = pd.DataFrame([{
                    "Date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "White": white, 
                    "Black": black, 
                    "Result": result,
                    "Event": event
                }])
                updated_matches = pd.concat([matches_df, new_match], ignore_index=True)
                
                conn.update(worksheet="players", data=players_df)
                conn.update(worksheet="matches", data=updated_matches)
                
                st.cache_data.clear()
                st.success(f"Match logged! {white} is now {new_w_elo} and {black} is now {new_b_elo}.")

# --- PAGE 4: ADD PLAYER ---
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

# --- PAGE 5: MANAGE DATA ---
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
                
                conn.update(worksheet="players", data=players_df)
                conn.update(worksheet="matches", data=matches_df)
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
            
