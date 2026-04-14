import streamlit as st
import requests
from groq import Groq
import os
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title=\"Smart Global Insights Dashboard\",
    page_icon=\"🌍\",
    layout=\"wide\",
    initial_sidebar_state=\"expanded\"
)

# Custom CSS for light/clean theme
st.markdown(\"\"\"
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        border: none;
        font-weight: 500;
    }
    .stButton>button:hover {
        background-color: #45a049;
    }
    .news-card {
        background-color: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        text-align: center;
    }
    .aqi-good { color: #4CAF50; font-weight: bold; }
    .aqi-moderate { color: #FFC107; font-weight: bold; }
    .aqi-unhealthy { color: #FF9800; font-weight: bold; }
    .aqi-very-unhealthy { color: #F44336; font-weight: bold; }
    .aqi-hazardous { color: #9C27B0; font-weight: bold; }
    h1 { color: #2c3e50; }
    h2 { color: #34495e; }
    h3 { color: #4a5568; }
    </style>
\"\"\", unsafe_allow_html=True)

# Load API keys from secrets or environment
try:
    GROQ_API_KEY = st.secrets.get(\"GROQ_API_KEY\", os.getenv(\"GROQ_API_KEY\", \"\"))
    NEWS_API_KEY = st.secrets.get(\"NEWS_API_KEY\", os.getenv(\"NEWS_API_KEY\", \"\"))
    WEATHER_API_KEY = st.secrets.get(\"WEATHER_API_KEY\", os.getenv(\"WEATHER_API_KEY\", \"\"))
except:
    GROQ_API_KEY = os.getenv(\"GROQ_API_KEY\", \"\")
    NEWS_API_KEY = os.getenv(\"NEWS_API_KEY\", \"\")
    WEATHER_API_KEY = os.getenv(\"WEATHER_API_KEY\", \"\")

# Initialize Groq client if API key is available
groq_client = None
if GROQ_API_KEY:
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
    except Exception as e:
        st.sidebar.warning(f\"Groq initialization failed: {str(e)}\")

# Helper Functions

def fetch_news(category=\"general\", country=\"us\", page_size=5):
    \"\"\"Fetch latest news from News API\"\"\"
    if not NEWS_API_KEY:
        return {\"error\": \"News API key not configured. Please add it to Streamlit secrets.\"}
    
    try:
        url = f\"https://newsapi.org/v2/top-headlines\"
        params = {
            \"country\": country.lower(),
            \"category\": category,
            \"pageSize\": page_size,
            \"apiKey\": NEWS_API_KEY
        }
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 401:
            return {\"error\": \"Invalid News API key. Please check your API key in Streamlit secrets.\"}
        elif response.status_code == 400:
            return {\"error\": f\"Invalid country code '{country}'. Please use 2-letter country codes (e.g., us, in, gb, fr, de).\"}
        elif response.status_code == 429:
            return {\"error\": \"News API rate limit exceeded. Please try again later.\"}
        
        response.raise_for_status()
        data = response.json()
        
        # Add debug info
        if data.get(\"totalResults\", 0) == 0:
            return {\"error\": f\"No articles found for country '{country}' in category '{category}'. Try a different combination.\"}
        
        return data
    except Exception as e:
        return {\"error\": f\"News API error: {str(e)}\"}

def summarize_with_groq(text):
    \"\"\"Summarize text using Groq API with LLaMA3\"\"\"
    if not groq_client:
        # Fallback: return first 2 sentences
        sentences = text.split('. ')[:2]
        return '. '.join(sentences) + '.' if sentences else text[:200]
    
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    \"role\": \"system\",
                    \"content\": \"You are a helpful assistant that summarizes news articles concisely in 2-3 sentences.\"
                },
                {
                    \"role\": \"user\",
                    \"content\": f\"Summarize this news article concisely:

{text}\"
                }
            ],
            model=\"llama3-8b-8192\",
            temperature=0.5,
            max_tokens=150
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        # Fallback on error
        sentences = text.split('. ')[:2]
        return '. '.join(sentences) + '.' if sentences else text[:200]

def fetch_weather(city):
    \"\"\"Fetch weather data from OpenWeatherMap API\"\"\"
    if not WEATHER_API_KEY:
        return {\"error\": \"Weather API key not configured. Please add it to Streamlit secrets.\"}
    
    try:
        url = f\"https://api.openweathermap.org/data/2.5/weather\"
        params = {
            \"q\": city,
            \"appid\": WEATHER_API_KEY,
            \"units\": \"metric\"
        }
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 401:
            return {
                \"error\": \"OpenWeatherMap API key is invalid or not activated yet.\",
                \"help\": \"If you just created the key, wait 10-15 minutes for activation. Then refresh this page.\"
            }
        elif response.status_code == 404:
            return {\"error\": f\"City '{city}' not found. Please check the spelling.\"}
        elif response.status_code == 429:
            return {\"error\": \"API rate limit exceeded. Please try again later.\"}
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        return {\"error\": f\"Weather API error: {str(e)}\"}
    except Exception as e:
        return {\"error\": f\"Connection error: {str(e)}\"}

def fetch_aqi(city):
    \"\"\"Fetch Air Quality Index using OpenWeatherMap API\"\"\"
    if not WEATHER_API_KEY:
        return {\"error\": \"Weather API key not configured. Please add it to Streamlit secrets.\"}
    
    try:
        # First get coordinates
        geo_url = f\"http://api.openweathermap.org/geo/1.0/direct\"
        geo_params = {
            \"q\": city,
            \"limit\": 1,
            \"appid\": WEATHER_API_KEY
        }
        geo_response = requests.get(geo_url, params=geo_params, timeout=10)
        
        if geo_response.status_code == 401:
            return {
                \"error\": \"OpenWeatherMap API key is invalid or not activated yet.\",
                \"help\": \"If you just created the key, wait 10-15 minutes for activation. Then refresh this page.\"
            }
        
        geo_response.raise_for_status()
        geo_data = geo_response.json()
        
        if not geo_data:
            return {\"error\": f\"City '{city}' not found. Please check the spelling.\"}
        
        lat = geo_data[0][\"lat\"]
        lon = geo_data[0][\"lon\"]
        
        # Get AQI data
        aqi_url = f\"http://api.openweathermap.org/data/2.5/air_pollution\"
        aqi_params = {
            \"lat\": lat,
            \"lon\": lon,
            \"appid\": WEATHER_API_KEY
        }
        aqi_response = requests.get(aqi_url, params=aqi_params, timeout=10)
        aqi_response.raise_for_status()
        return aqi_response.json()
    except requests.exceptions.HTTPError as e:
        return {\"error\": f\"AQI API error: {str(e)}\"}
    except Exception as e:
        return {\"error\": f\"Connection error: {str(e)}\"}

def get_aqi_category(aqi):
    \"\"\"Get AQI category and color class\"\"\"
    if aqi == 1:
        return \"Good\", \"aqi-good\"
    elif aqi == 2:
        return \"Moderate\", \"aqi-moderate\"
    elif aqi == 3:
        return \"Unhealthy for Sensitive Groups\", \"aqi-unhealthy\"
    elif aqi == 4:
        return \"Unhealthy\", \"aqi-very-unhealthy\"
    else:
        return \"Very Unhealthy/Hazardous\", \"aqi-hazardous\"

# Sidebar Navigation
st.sidebar.title(\"🌍 Navigation\")
page = st.sidebar.radio(
    \"Go to\",
    [\"Dashboard\", \"News\", \"Weather\", \"Air Quality\"]
)

st.sidebar.markdown(\"---\")

# API Key Status Indicator
st.sidebar.subheader(\"🔑 API Status\")
if GROQ_API_KEY:
    st.sidebar.success(\"✅ Groq API\")
else:
    st.sidebar.warning(\"⚠️ Groq API (optional)\")

if NEWS_API_KEY:
    st.sidebar.success(\"✅ News API\")
else:
    st.sidebar.error(\"❌ News API\")

if WEATHER_API_KEY:
    st.sidebar.success(\"✅ Weather API\")
else:
    st.sidebar.error(\"❌ Weather API\")

st.sidebar.markdown(\"---\")
st.sidebar.info(\"\"\"
**Smart Global Insights Dashboard**

Stay updated with:
- 📰 Latest News
- 🌦 Weather Updates
- 🌫 Air Quality Index
- 🤖 AI-Powered Summaries
\"\"\")

# Main Content

if page == \"Dashboard\":
    st.title(\"🌍 Smart Global Insights Dashboard\")
    st.markdown(f\"*Last updated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}*\")
    st.markdown(\"---\")
    
    # Top News
    st.header(\"📰 Top Headlines\")
    news_data = fetch_news(page_size=3)
    
    if \"error\" in news_data:
        st.error(f\"❌ {news_data['error']}\")
    elif news_data.get(\"articles\"):
        for article in news_data[\"articles\"][:3]:
            col1, col2 = st.columns([1, 3])
            with col1:
                if article.get(\"urlToImage\"):
                    st.image(article[\"urlToImage\"], use_container_width=True)
            with col2:
                st.subheader(article.get(\"title\", \"No title\"))
                st.caption(f\"Source: {article.get('source', {}).get('name', 'Unknown')}\")
                if article.get(\"description\"):
                    st.write(article[\"description\"][:150] + \"...\")
            st.markdown(\"---\")
    else:
        st.info(\"No news articles available\")
    
    # Weather & AQI
    col1, col2 = st.columns(2)
    
    with col1:
        st.header(\"🌦 Weather - Hyderabad\")
        weather_data = fetch_weather(\"Hyderabad\")
        
        if \"error\" in weather_data:
            st.error(f\"❌ {weather_data['error']}\")
            if \"help\" in weather_data:
                st.info(f\"💡 {weather_data['help']}\")
        else:
            temp = weather_data[\"main\"][\"temp\"]
            humidity = weather_data[\"main\"][\"humidity\"]
            condition = weather_data[\"weather\"][0][\"description\"].title()
            
            st.metric(\"Temperature\", f\"{temp}°C\")
            st.metric(\"Humidity\", f\"{humidity}%\")
            st.metric(\"Condition\", condition)
    
    with col2:
        st.header(\"🌫 Air Quality - Hyderabad\")
        aqi_data = fetch_aqi(\"Hyderabad\")
        
        if \"error\" in aqi_data:
            st.error(f\"❌ {aqi_data['error']}\")
            if \"help\" in aqi_data:
                st.info(f\"💡 {aqi_data['help']}\")
        else:
            aqi_value = aqi_data[\"list\"][0][\"main\"][\"aqi\"]
            category, color_class = get_aqi_category(aqi_value)
            
            st.metric(\"AQI Level\", aqi_value)
            st.markdown(f\"<p class='{color_class}' style='font-size: 1.5rem;'>{category}</p>\", unsafe_allow_html=True)

elif page == \"News\":
    st.title(\"📰 Global News\")
    
    # Country codes mapping
    popular_countries = {
        \"🇺🇸 United States\": \"us\",
        \"🇮🇳 India\": \"in\",
        \"🇬🇧 United Kingdom\": \"gb\",
        \"🇨🇦 Canada\": \"ca\",
        \"🇦🇺 Australia\": \"au\",
        \"🇫🇷 France\": \"fr\",
        \"🇩🇪 Germany\": \"de\",
        \"🇯🇵 Japan\": \"jp\",
        \"🇧🇷 Brazil\": \"br\",
        \"🇲🇽 Mexico\": \"mx\",
        \"🇮🇹 Italy\": \"it\",
        \"🇪🇸 Spain\": \"es\",
        \"🇨🇳 China\": \"cn\",
        \"🇷🇺 Russia\": \"ru\",
        \"🇰🇷 South Korea\": \"kr\",
        \"Custom (Enter Code)\": \"custom\"
    }
    
    # Filters
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        category = st.selectbox(
            \"📂 Category\",
            [\"general\", \"business\", \"technology\", \"sports\", \"entertainment\", \"health\", \"science\"]
        )
    
    with col2:
        selected_country_name = st.selectbox(
            \"🌍 Country\",
            list(popular_countries.keys())
        )
        
        # Get the country code
        if popular_countries[selected_country_name] == \"custom\":
            country_code = None  # Will be set by text input below
        else:
            country_code = popular_countries[selected_country_name]
    
    # Custom country code input
    if selected_country_name == \"Custom (Enter Code)\":
        st.info(\"💡 **Tip:** Use 2-letter country codes. Examples: ae (UAE), sg (Singapore), nl (Netherlands), ch (Switzerland)\")
        custom_country = st.text_input(
            \"Enter 2-letter country code:\",
            placeholder=\"e.g., ae, sg, nl, ch\",
            max_chars=2
        )
        if custom_country:
            country_code = custom_country.lower().strip()
        else:
            country_code = \"us\"  # Default
    
    with col3:
        st.write(\"\")  # Spacing
        st.write(\"\")  # Spacing
        if st.button(\"🔄 Refresh\", use_container_width=True):
            st.rerun()
    
    st.markdown(\"---\")
    
    # Display selected filters
    st.caption(f\"📍 Showing **{category}** news from **{selected_country_name.split(' ', 1)[-1] if selected_country_name != 'Custom (Enter Code)' else country_code.upper()}**\")
    
    # Fetch news
    news_data = fetch_news(category=category, country=country_code, page_size=10)
    
    if \"error\" in news_data:
        st.error(f\"❌ {news_data['error']}\")
        st.info(\"💡 Try selecting a different category or country. Not all countries have articles in all categories.\")
    elif news_data.get(\"articles\"):
        st.success(f\"Found {news_data.get('totalResults', 0)} articles\")
        
        for idx, article in enumerate(news_data[\"articles\"]):
            st.markdown(f\"<div class='news-card'>\", unsafe_allow_html=True)
            
            col1, col2 = st.columns([1, 2])
            
            with col1:
                if article.get(\"urlToImage\"):
                    try:
                        st.image(article[\"urlToImage\"], use_container_width=True)
                    except:
                        st.info(\"📰 Image unavailable\")
                else:
                    st.info(\"📰 No image\")
            
            with col2:
                st.subheader(article.get(\"title\", \"No title\"))
                st.caption(f\"📌 Source: {article.get('source', {}).get('name', 'Unknown')}\")
                
                if article.get(\"description\"):
                    st.write(article[\"description\"])
                
                # Summarize button
                if st.button(f\"✨ Summarize\", key=f\"summarize_{idx}\"):
                    with st.spinner(\"Generating AI summary...\"):
                        content = article.get(\"content\") or article.get(\"description\") or article.get(\"title\")
                        summary = summarize_with_groq(content)
                        st.success(\"**AI Summary:**\")
                        st.write(summary)
                
                if article.get(\"url\"):
                    st.markdown(f\"[Read full article →]({article['url']})\")
            
            st.markdown(\"</div>\", unsafe_allow_html=True)
            st.markdown(\"<br>\", unsafe_allow_html=True)
    else:
        st.info(\"No news articles available for this category and country\")

elif page == \"Weather\":
    st.title(\"🌦 Weather Information\")
    
    city = st.text_input(\"Enter city name:\", value=\"Hyderabad\")
    
    if st.button(\"🔍 Get Weather\") or city:
        weather_data = fetch_weather(city)
        
        if \"error\" in weather_data:
            st.error(f\"❌ {weather_data['error']}\")
            if \"help\" in weather_data:
                st.info(f\"💡 {weather_data['help']}\")
        else:
            st.success(f\"Weather data for **{weather_data['name']}, {weather_data['sys']['country']}**\")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown(\"<div class='metric-card'>\", unsafe_allow_html=True)
                st.metric(
                    \"🌡 Temperature\",
                    f\"{weather_data['main']['temp']}°C\",
                    f\"Feels like {weather_data['main']['feels_like']}°C\"
                )
                st.markdown(\"</div>\", unsafe_allow_html=True)
            
            with col2:
                st.markdown(\"<div class='metric-card'>\", unsafe_allow_html=True)
                st.metric(\"💧 Humidity\", f\"{weather_data['main']['humidity']}%\")
                st.markdown(\"</div>\", unsafe_allow_html=True)
            
            with col3:
                st.markdown(\"<div class='metric-card'>\", unsafe_allow_html=True)
                st.metric(\"🌪 Pressure\", f\"{weather_data['main']['pressure']} hPa\")
                st.markdown(\"</div>\", unsafe_allow_html=True)
            
            st.markdown(\"---\")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader(\"Weather Condition\")
                st.write(f\"**{weather_data['weather'][0]['description'].title()}**\")
                st.write(f\"☁️ Clouds: {weather_data['clouds']['all']}%\")
            
            with col2:
                st.subheader(\"Wind Information\")
                st.write(f\"💨 Speed: {weather_data['wind']['speed']} m/s\")
                if 'deg' in weather_data['wind']:
                    st.write(f\"🧭 Direction: {weather_data['wind']['deg']}°\")

elif page == \"Air Quality\":
    st.title(\"🌫 Air Quality Index (AQI)\")
    
    city = st.text_input(\"Enter city name:\", value=\"Hyderabad\")
    
    if st.button(\"🔍 Get AQI\") or city:
        aqi_data = fetch_aqi(city)
        
        if \"error\" in aqi_data:
            st.error(f\"❌ {aqi_data['error']}\")
            if \"help\" in aqi_data:
                st.info(f\"💡 {aqi_data['help']}\")
        else:
            aqi_value = aqi_data[\"list\"][0][\"main\"][\"aqi\"]
            category, color_class = get_aqi_category(aqi_value)
            components = aqi_data[\"list\"][0][\"components\"]
            
            st.success(f\"Air Quality data for **{city.title()}**\")
            
            # Main AQI display
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.markdown(\"<div class='metric-card'>\", unsafe_allow_html=True)
                st.metric(\"AQI Level\", aqi_value)
                st.markdown(\"</div>\", unsafe_allow_html=True)
            
            with col2:
                st.markdown(\"<div class='metric-card'>\", unsafe_allow_html=True)
                st.markdown(f\"<h2 class='{color_class}'>{category}</h2>\", unsafe_allow_html=True)
                st.markdown(\"</div>\", unsafe_allow_html=True)
            
            st.markdown(\"---\")
            
            # Pollutant details
            st.subheader(\"Pollutant Levels (μg/m³)\")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(\"CO\", f\"{components.get('co', 0):.2f}\")
                st.metric(\"NO₂\", f\"{components.get('no2', 0):.2f}\")
            
            with col2:
                st.metric(\"O₃\", f\"{components.get('o3', 0):.2f}\")
                st.metric(\"SO₂\", f\"{components.get('so2', 0):.2f}\")
            
            with col3:
                st.metric(\"PM2.5\", f\"{components.get('pm2_5', 0):.2f}\")
                st.metric(\"PM10\", f\"{components.get('pm10', 0):.2f}\")
            
            st.markdown(\"---\")
            
            # AQI Scale Reference
            st.subheader(\"AQI Scale Reference\")
            st.markdown(\"\"\"
            - <span class='aqi-good'>1 - Good</span>: Air quality is satisfactory
            - <span class='aqi-moderate'>2 - Moderate</span>: Acceptable air quality
            - <span class='aqi-unhealthy'>3 - Unhealthy for Sensitive Groups</span>
            - <span class='aqi-very-unhealthy'>4 - Unhealthy</span>: Everyone may experience health effects
            - <span class='aqi-hazardous'>5 - Very Unhealthy/Hazardous</span>: Health alert
            \"\"\", unsafe_allow_html=True)

# Footer
st.markdown(\"---\")
st.markdown(\"\"\"
<div style='text-align: center; color: #7f8c8d; padding: 1rem;'>
    <p>Smart Global Insights Dashboard | Powered by Groq AI, News API, and OpenWeatherMap</p>
</div>
\"\"\", unsafe_allow_html=True)
"
