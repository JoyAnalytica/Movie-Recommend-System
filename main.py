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
# CORS Config
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# Load Movie Recommendation Model
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

movie_list_path = os.path.join(BASE_DIR, "movie_list_pkl")
similarity_path = os.path.join(BASE_DIR, "similarity.pkl")

# Load movie dataset
new = pickle.load(open(movie_list_path, "rb"))

# Ensure 'title_lower' column exists for search optimization
if "title_lower" not in new.columns:
    new["title_lower"] = new["title"].str.lower()

# Load similarity matrix safely
try:
    similarity = pickle.load(open(similarity_path, "rb"))
except FileNotFoundError:
    similarity = None
    print("Warning: similarity.pkl not found. Fallback recommendations enabled.")


# =========================================================
# Root Route (Home)
# =========================================================

@app.get("/")
def home():
    return {
        "status": "online",
        "message": "Welcome to the Movie Recommendation API!",
        "endpoints": {
            "docs": "/docs",
            "recommend": "/recommend (POST)",
            "search": "/search?q=movie_name (GET)",
            "movies": "/movies (GET)"
        }
    }


# =========================================================
# Input Schema
# =========================================================

class Movie(BaseModel):
    movie: str


# =========================================================
# Fetch Movie Poster from TMDB
# =========================================================

def fetch_poster(movie_id):
    if not TMDB_API_KEY:
        return None

    url = (
        f"https://api.themoviedb.org/3/movie/{movie_id}"
        f"?api_key={TMDB_API_KEY}&language=en-US"
    )

    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        poster_path = data.get("poster_path")

        if poster_path:
            return f"https://image.tmdb.org/t/p/w500{poster_path}"
    except Exception as e:
        print(f"Error fetching poster: {e}")

    return None


# =========================================================
# Movie Recommendation Function
# =========================================================

def recommend(movie):
    # Case-insensitive movie matching
    matches = new[new["title"].str.lower() == movie.strip().lower()]

    if matches.empty:
        return None

    index = matches.index[0]
    recommended_indices = []

    # Option A: If similarity matrix is loaded, calculate Cosine Similarity
    if similarity is not None:
        distances = sorted(
            list(enumerate(similarity[index])),
            reverse=True,
            key=lambda x: x[1]
        )
        recommended_indices = [i[0] for i in distances[1:6]]
    
    # Option B: Fallback if similarity.pkl is missing on Render
    else:
        print("Similarity matrix missing. Generating fallback recommendations.")
        total_movies = len(new)
        recommended_indices = [(index + i + 1) % total_movies for i in range(5)]

    result = []
    for i in recommended_indices:
        movie_name = new.iloc[i].title
        movie_id = new.iloc[i].movie_id
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
            detail=f"Movie '{data.movie}' not found in database."
        )

    return {
        "movie": data.movie,
        "recommendations": result
    }


# =========================================================
# Movie Title Search (Autocomplete)
# =========================================================

@app.get("/search")
def search_movies(q: str, limit: int = 8):
    q = q.strip().lower()
    limit = max(1, min(limit, 15))

    if len(q) < 2:
        return {"results": []}

    starts_mask = new["title_lower"].str.startswith(q)
    contains_mask = new["title_lower"].str.contains(q, regex=False)

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