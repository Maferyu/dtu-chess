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
page = st.sidebar.radio("Navigation", ["Leaderboard", "Log a Match", "Add New Player"])

# --- PAGE 1: LEADERBOARD ---
if page == "Leaderboard":
    st.header("Current Standings")
    
    if players_df.empty:
        st.info("No players yet! Add some players to get started.")
    else:
        # Sort by ELO and reset index for rank numbers
        leaderboard = players_df.sort_values(by="ELO", ascending=False).reset_index(drop=True)
        leaderboard.index = leaderboard.index + 1
        
        # Keep only the columns we want to show
        leaderboard = leaderboard[['Name', 'ELO', 'Matches']]
        
        # Display with specific formatting to fix the 0.0000 issue
        st.dataframe(
            leaderboard.style.format({'ELO': '{:.1f}', 'Matches': '{:.0f}'}), 
            width="stretch"
        )
        
    st.subheader("Recent Matches")
    if not matches_df.empty:
        # Show last 5 matches reversed
        st.dataframe(matches_df.iloc[::-1].head(5), width="stretch")
    else:
        st.info("No matches played yet.")

# --- PAGE 2: LOG A MATCH ---
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
            password = st.text_input("Club Password", type="password")
            
            if st.button("Submit Result"):
                if password != "dtu2026": 
                    st.error("Incorrect password!")
                else:
                    # Get current ELOs and Matches played
                    w_idx = players_df.index[players_df['Name'] == white].tolist()[0]
                    b_idx = players_df.index[players_df['Name'] == black].tolist()[0]
                    
                    w_elo = float(players_df.at[w_idx, 'ELO'])
                    b_elo = float(players_df.at[b_idx, 'ELO'])
                    
                    # Determine score multiplier
                    score = 1 if "White Wins" in result else (0.5 if "Draw" in result else 0)
                    
                    # Calculate new ELOs
                    new_w_elo, new_b_elo = calculate_elo(w_elo, b_elo, score)
                    
                    # Update Players DataFrame
                    players_df.at[w_idx, 'ELO'] = new_w_elo
                    players_df.at[w_idx, 'Matches'] = int(players_df.at[w_idx, 'Matches']) + 1
                    
                    players_df.at[b_idx, 'ELO'] = new_b_elo
                    players_df.at[b_idx, 'Matches'] = int(players_df.at[b_idx, 'Matches']) + 1
                    
                    # Update Matches DataFrame
                    new_match = pd.DataFrame([{"White": white, "Black": black, "Result": result}])
                    updated_matches = pd.concat([matches_df, new_match], ignore_index=True)
                    
                    # Push updates to Google Sheets
                    conn.update(worksheet="players", data=players_df)
                    conn.update(worksheet="matches", data=updated_matches)
                    
                    # NUKE THE CACHE SO IT FETCHES FRESH DATA ON NEXT LOAD
                    st.cache_data.clear()
                    
                    st.success(f"Match logged! {white} is now {new_w_elo} and {black} is now {new_b_elo}.")

# --- PAGE 3: ADD PLAYER ---
elif page == "Add New Player":
    st.header("Register New Player")
    new_name = st.text_input("Player Name")
    starting_elo = st.number_input("Starting ELO", value=1200)
    
    if st.button("Add Player"):
        if new_name in players_df['Name'].values:
            st.error("Player already exists!")
        elif new_name:
            # Create a new row
            new_player = pd.DataFrame([{
                "Name": new_name, 
                "ELO": starting_elo, 
                "Matches": 0, 
                "Creation Date": datetime.now().strftime("%Y-%m-%d")
            }])
            
            # Append and update Google Sheet
            updated_players = pd.concat([players_df, new_player], ignore_index=True)
            conn.update(worksheet="players", data=updated_players)
            
            # NUKE THE CACHE
            st.cache_data.clear()
            
            st.success(f"Added {new_name} to the club with {starting_elo} ELO!")
