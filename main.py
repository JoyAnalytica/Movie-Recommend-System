import os
import pickle
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# =========================================================
# Load Environment Variables
# =========================================================

load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")


# =========================================================
# FastAPI App
# =========================================================

app = FastAPI(title="Movie Recommendation API")


# =========================================================
# CORS (needed so the frontend can call this API)
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # development only; use your frontend URL in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# Load Movie Recommendation Model
# =========================================================

# বর্তমান ফাইলের ডিরেক্টরি বের করার জন্য
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# movie_list_pkl ফাইলে ডট নেই, তাই নাম এভাবে হবে
movie_list_path = os.path.join(BASE_DIR, "movie_list_pkl")
similarity_path = os.path.join(BASE_DIR, "similarity.pkl")

new = pickle.load(open(movie_list_path, "rb"))
similarity = pickle.load(open(similarity_path, "rb"))

# Lowercase titles, prepared once for fast autocomplete search
new["title_lower"] = new["title"].str.lower()


# =========================================================
# Input Schema
# =========================================================

class Movie(BaseModel):
    movie: str


# =========================================================
# Fetch Movie Poster from TMDB
# =========================================================

def fetch_poster(movie_id):
    url = (
        f"https://api.themoviedb.org/3/movie/{movie_id}"
        f"?api_key={TMDB_API_KEY}&language=en-US"
    )

    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        poster_path = data.get("poster_path")

        if poster_path:
            # poster_path already starts with "/"
            return f"https://image.tmdb.org/t/p/w500{poster_path}"
    except Exception as e:
        print(f"Error fetching poster: {e}")

    return None


# =========================================================
# Movie Recommendation Function
# =========================================================

def recommend(movie):
    # Check if movie exists in dataframe
    matches = new[new["title"].str.lower() == movie.strip().lower()]

    if matches.empty:
        return None

    # Find the index of selected movie
    index = matches.index[0]

    # Calculate similarity distances
    distances = sorted(
        list(enumerate(similarity[index])),
        reverse=True,
        key=lambda x: x[1]
    )

    result = []

    # Get Top 5 Recommendations
    for i in distances[1:6]:
        movie_name = new.iloc[i[0]].title
        movie_id = new.iloc[i[0]].movie_id

        # Get movie poster from TMDB
        poster = fetch_poster(movie_id)

        result.append({
            "title": movie_name,
            "poster": poster
        })

    return result


# =========================================================
# Recommendation API Endpoint
# =========================================================

@app.post("/recommend")
def get_recommendation(data: Movie):
    result = recommend(data.movie)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Movie '{data.movie}' not found in the database."
        )

    return {
        "movie": data.movie,
        "recommendations": result
    }


# =========================================================
# Movie Title Search (autocomplete)
# =========================================================

@app.get("/search")
def search_movies(q: str, limit: int = 8):
    q = q.strip().lower()
    limit = max(1, min(limit, 15))

    if len(q) < 2:
        return {"results": []}

    starts_mask = new["title_lower"].str.startswith(q)
    contains_mask = new["title_lower"].str.contains(q, regex=False)

    # Titles that start with the text come first, then titles that contain it
    results = new.loc[starts_mask, "title"].head(limit).tolist()
    if len(results) < limit:
        extra = new.loc[contains_mask & ~starts_mask, "title"].head(limit - len(results)).tolist()
        results += extra

    return {"results": results}


# =========================================================
# List All Movies
# =========================================================

@app.get("/movies")
def list_movies():
    titles = sorted(new["title"].tolist())
    return {"count": len(titles), "movies": titles}