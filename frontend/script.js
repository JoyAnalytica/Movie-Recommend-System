const API_URL = "http://127.0.0.1:8000/recommend";

const input = document.getElementById("movieInput");
const searchBtn = document.getElementById("searchBtn");
const results = document.getElementById("results");

/* Small helper: build an element with class and optional HTML/text */
function el(tag, className, html) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (html) node.innerHTML = html;
  return node;
}

function showState(icon, title, message, extraClass = "") {
  results.innerHTML = "";
  const box = el("div", `state ${extraClass}`);
  box.innerHTML = `<i class="fa-solid ${icon}"></i>`;
  box.append(el("h2", "", ""), el("p", ""));
  box.querySelector("h2").textContent = title;
  box.querySelector("p").textContent = message;
  results.appendChild(box);
}

function resetResults() {
  showState(
    "fa-film",
    "Find Your Next Favorite Movie",
    "Enter a movie you love and we'll recommend something you'll enjoy."
  );
}

function showLoading() {
  results.innerHTML = `
    <div class="state">
      <div class="spinner"></div>
      <h2>Finding movies for you<span class="dots"><span>.</span><span>.</span><span>.</span></span></h2>
    </div>`;
  searchBtn.disabled = true;
  searchBtn.textContent = "Searching...";
}

function hideLoading() {
  searchBtn.disabled = false;
  searchBtn.textContent = "Search";
}

function showError(title, message) {
  showState("fa-triangle-exclamation", title, message, "error");
}

function createCard(movie, index) {
  const card = el("article", "card");
  const poster = el("div", "poster");

  const fallback = () => {
    poster.innerHTML = `<div class="fallback"><i class="fa-solid fa-film"></i><span></span></div>`;
    poster.querySelector("span").textContent = movie.title;
  };

  if (movie.poster) {
    const img = new Image();
    img.alt = `${movie.title} poster`;
    img.loading = "lazy";
    img.onerror = fallback;
    img.src = movie.poster;
    poster.appendChild(img);
  } else {
    fallback();
  }

  const rank = el("span", "rank");
  rank.textContent = String(index + 1).padStart(2, "0");
  const badge = el("span", "badge", `<i class="fa-solid fa-star"></i> Recommended`);
  const title = el("h3");
  title.textContent = movie.title;

  card.append(poster, rank, badge, title);
  return card;
}

function displayRecommendations(data) {
  results.innerHTML = "";
  const header = el("div");
  header.append(el("h2", "results-title"), el("p", "results-sub"));
  header.querySelector("h2").textContent = "Recommended For You";
  header.querySelector("p").innerHTML = "Because you searched for <b></b>";
  header.querySelector("b").textContent = data.movie;

  const grid = el("div", "grid");
  data.recommendations.forEach((movie, i) => grid.appendChild(createCard(movie, i)));

  results.append(header, grid);
}

async function getRecommendations() {
  const movieName = input.value.trim();

  if (!movieName) {
    showError("Please enter a movie name.", "Type a title you like, then press Search.");
    return;
  }

  showLoading();

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ movie: movieName })
    });

    if (response.status === 404) {
      showError("Movie not found", "Please check the movie name and try again.");
      return;
    }
    if (!response.ok) {
      throw new Error(`Server responded with status ${response.status}`);
    }

    const data = await response.json();
    if (!data.recommendations || data.recommendations.length === 0) {
      showError("No recommendations found", "Try a different movie title.");
      return;
    }

    displayRecommendations(data);
    document.getElementById("recommendations").scrollIntoView({ behavior: "smooth" });
  } catch (error) {
    console.error(error);
    showError(
      "Unable to connect to the recommendation server.",
      "Please make sure the FastAPI backend is running."
    );
  } finally {
    hideLoading();
  }
}

/* ---------- Autocomplete ---------- */
const SEARCH_URL = "http://127.0.0.1:8000/search";
const list = document.getElementById("suggestions");
let activeIndex = -1;
let debounceTimer;
let latestRequest = 0;

function hideSuggestions() {
  list.hidden = true;
  list.innerHTML = "";
  activeIndex = -1;
}

function setActive(i) {
  const items = list.querySelectorAll("li");
  items.forEach((li, n) => li.classList.toggle("active", n === i));
  activeIndex = i;
  if (items[i]) items[i].scrollIntoView({ block: "nearest" });
}

function selectSuggestion(title) {
  input.value = title;
  hideSuggestions();
  getRecommendations();
}

function renderSuggestions(titles) {
  list.innerHTML = "";
  activeIndex = -1;
  if (!titles.length) { list.hidden = true; return; }
  titles.forEach((title) => {
    const li = el("li", "", `<i class="fa-solid fa-film"></i>`);
    li.append(document.createTextNode(title));
    li.setAttribute("role", "option");
    // mousedown fires before the input loses focus
    li.addEventListener("mousedown", (e) => { e.preventDefault(); selectSuggestion(title); });
    list.appendChild(li);
  });
  list.hidden = false;
}

async function fetchSuggestions(query) {
  const requestId = ++latestRequest;
  try {
    const res = await fetch(`${SEARCH_URL}?q=${encodeURIComponent(query)}`);
    if (!res.ok) return;
    const data = await res.json();
    if (requestId === latestRequest) renderSuggestions(data.results || []);
  } catch (err) {
    hideSuggestions();
  }
}

input.addEventListener("input", () => {
  clearTimeout(debounceTimer);
  const query = input.value.trim();
  if (query.length < 2) { latestRequest++; hideSuggestions(); return; }
  debounceTimer = setTimeout(() => fetchSuggestions(query), 200);
});

input.addEventListener("keydown", (e) => {
  const items = list.querySelectorAll("li");
  if (e.key === "ArrowDown" && items.length) {
    e.preventDefault();
    setActive((activeIndex + 1) % items.length);
  } else if (e.key === "ArrowUp" && items.length) {
    e.preventDefault();
    setActive((activeIndex - 1 + items.length) % items.length);
  } else if (e.key === "Escape") {
    hideSuggestions();
  } else if (e.key === "Enter") {
    if (activeIndex >= 0 && items[activeIndex]) {
      selectSuggestion(items[activeIndex].textContent);
    } else {
      hideSuggestions();
      getRecommendations();
    }
  }
});

document.addEventListener("click", (e) => {
  if (!e.target.closest(".search-wrap")) hideSuggestions();
});

searchBtn.addEventListener("click", () => { hideSuggestions(); getRecommendations(); });

resetResults();