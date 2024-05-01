import aiohttp
import asyncio
import random
from datetime import datetime, timedelta
import json
from twikit import Client
from twikit.errors import TweetNotAvailable, TooManyRequests

# Load Twitter credentials (replace these with your own)
USERNAME = "your_twitter_username"
EMAIL = "your_email@example.com"
PASSWORD = "your_twitter_password"
COOKIES_FILE_PATH = "cookies.json"  # Path to store cookies
STATE_FILE_PATH = "state.json"  # Path to store bot state

# List of Twitter usernames to search and reply to
usernames_to_search = ["user1", "user2", "user3"]  # Add or remove usernames as needed
json_file_path = "replied_tweets.json"  # Path to store replied tweets
instructions_file_path = "instructions.txt"  # Path to instructions for GPT-3.5

# Rate limits for each endpoint (adjust as needed)
rate_limits = {
    "SearchTimeline": 50,
    "media.upload": 615,
    "cards.create": None,
    "CreateTweet": None,
    "CreateScheduledTweet": 500,
    "DeleteTweet": None,
    "UserByScreenName": 95,
    "UserByRestId": 500,
    "TweetDetail": 150,
    "Likes, UserMedia": 500,
    "UserTweetsAndReplies, UserTweets": 50,
    "HomeTimeline": 500,
    "FavoriteTweet": 500,
    "UnfavoriteTweet": 500,
    "CreateRetweet": None,
    "DeleteRetweet": None,
    "CreateBookmark": 500,
    "DeleteBookmark": 500,
    "Bookmarks": 500,
    "BookmarksAllDelete": 500,
    "friendships.create": None,
    "friendships.destroy": None,
    "guide": 20000,
    "Followers": 50,
    "BlueVerifiedFollowers": 500,
    "FollowersYouKnow": 500,
    "Following": 500,
    "UserCreatorSubscriptions": 500,
    "dm.new2": None,
    "DMMessageDeleteMutation": 500,
    "dm.conversation": 900,
    "Favoriters": 500,
    "Retweeters": 500
}

# Dictionary to store request counts
request_counts = {endpoint: 0 for endpoint in rate_limits}

# Last reset time for rate limits
last_reset_time = datetime.now()

# Flag to enable/disable the bot
bot_enabled = True

# Function to check if the bot should wait before making another request
def should_wait(endpoint):
    global last_reset_time
    reset_interval = timedelta(minutes=15)
    if datetime.now() - last_reset_time > reset_interval:
        # Reset request counts if more than 15 minutes have passed
        last_reset_time = datetime.now()
        for endpoint in request_counts:
            request_counts[endpoint] = 0
    if rate_limits[endpoint] is not None:
        if request_counts[endpoint] >= rate_limits[endpoint]:
            return True
    return False

# Function to increment request count for an endpoint
def increment_request_count(endpoint):
    request_counts[endpoint] += 1

# Function to load replied tweets from a JSON file
def load_replied_tweets():
    try:
        with open(json_file_path, 'r') as file:
            replied_tweets = json.load(file)
        return replied_tweets
    except FileNotFoundError:
        return {}

# Function to save replied tweet data to a JSON file
def save_replied_tweet(tweet_id, response):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    replied_tweets[tweet_id] = {"response": response, "timestamp": timestamp}
    with open(json_file_path, 'w') as file:
        json.dump(replied_tweets, file, indent=4)

# Function to load bot state from a JSON file
def load_state():
    try:
        with open(STATE_FILE_PATH, 'r') as file:
            state = json.load(file)
        return state
    except FileNotFoundError:
        return {"current_user": None, "replied_tweets_count": 0}

# Function to save bot state to a JSON file
def save_state(current_user, replied_tweets_count):
    state = {"current_user": current_user, "replied_tweets_count": replied_tweets_count}
    with open(STATE_FILE_PATH, 'w') as file:
        json.dump(state, file, indent=4)

# Function to generate a response using GPT-3.5 based on tweet content
async def generate_gpt_response(tweet_content):
    # Reading instructions from a file
    with open(instructions_file_path, "r", encoding="utf-8") as file:
        instructions = ""
        for line in file:
            instructions += line

    data = {
        "model": "mixtral-8x7b",
        "temperature": 0.4,
        "max_tokens": 100,
        "use_cache": True,
	    "stream": False,
        "messages": [
            {"role": "system", "content": instructions},
            {"role": "user", "content": tweet_content}
        ],
    }

    endpoint = "https://open-ai34.p.rapidapi.com/api/v1/chat/completions"

    headers = {
	    "content-type": "application/json",
	    "X-RapidAPI-Key": "805d125445msha59105dc87f29f4p1e1273jsn0cb50420b07a",
	    "X-RapidAPI-Host": "open-ai34.p.rapidapi.com"
    }

    try:
        async with aiohttp.ClientSession() as session:
            # Introduce random delay between 5 to 7 seconds
            await asyncio.sleep(random.uniform(5, 7))

            # Send request to ChatGPT API
            async with session.post(endpoint, headers=headers, json=data) as response:
                response_data = await response.json()
                choices = response_data["choices"]
                if choices:
                    return choices[0]["message"]["content"]
    except aiohttp.ClientError as error:
        print(f"Error making the request to GPT-3.5 API: {error}")

async def like_and_retweet(tweet):
    await asyncio.sleep(random.uniform(20, 30))  # Random delay between 20 and 30 seconds
    like_tweet(tweet)
    await asyncio.sleep(random.uniform(20, 30))  # Random delay between 20 and 30 seconds
    retweet_tweet(tweet)

# Function to like a tweet
def like_tweet(tweet):
    try:
        tweet.favorite()
        print("Tweet liked successfully.")
    except Exception as e:
        print(f"Error liking the tweet: {e}")

# Function to retweet a tweet
def retweet_tweet(tweet):
    try:
        tweet.retweet()
        print("Tweet retweeted successfully.")
    except Exception as e:
        print(f"Error retweeting the tweet: {e}")

async def reply_to_tweets(client, username):
    if not bot_enabled:
        print("Bot is currently disabled.")
        return

    # Get user by screen name
    user = client.get_user_by_screen_name(username)

    try:
        # Get user's latest tweets
        latest_tweets = user.get_tweets('Tweets', count=5)

        # Counter to keep track of replied tweets for the current user
        replied_tweets_count = 0

        for latest_tweet in latest_tweets:
            tweet_id = latest_tweet.id
            # Check if it's a retweet
            if hasattr(latest_tweet, 'retweeted_status'):
                continue  # Skip retweets
            if tweet_id not in replied_tweets:
                # Print the tweet information
                print(f"Tweet ID: {tweet_id}")
                print(f"Tweet Text: {latest_tweet.text}")

                # Generate GPT-3.5 response based on tweet content and instructions
                gpt_response = await generate_gpt_response(latest_tweet.text)

                # Reply to the tweet with the generated response
                try:
                    latest_tweet.reply(gpt_response)
                    print(f"Replied to the tweet successfully with GPT-3.5 generated response.")

                    # Save replied tweet information
                    save_replied_tweet(tweet_id, gpt_response)

                    # Increment the counter
                    replied_tweets_count += 1

                    # Check if the limit (e.g., 5 tweets) has been reached
                    if replied_tweets_count >= 5:
                        print(f"Replied to 5 tweets for user {username}. Moving to the next user.")
                        break

                    # Wait for a random time before the next reply
                    wait_time = random.uniform(20, 500)
                    print(f"Waiting for {wait_time:.2f} seconds before the next reply.")
                    await asyncio.sleep(wait_time)

                except Exception as e:
                    print(f"Error replying to the tweet: {e}")
            else:
                print(f"Tweet with ID {tweet_id} has already been replied to. Skipping.")

        # Introduce a 2-3 second random wait after processing each user's tweets
        wait_after_processing = random.uniform(2, 3)
        print(f"Waiting for {wait_after_processing:.2f} seconds after processing tweets for user {username}.")
        await asyncio.sleep(wait_after_processing)

    except TweetNotAvailable:
        print(f"No available tweets for user {username}.")
    except TooManyRequests as e:
        print(f"Rate limit hit: {e}. Retrying after 15 minutes.")
        await asyncio.sleep(900)  # 900 seconds = 15 minutes
        await reply_to_tweets(client, username)  # Retry the function after waiting
    except Exception as e:
        print(f"An error occurred: {e}")

async def main():
    global replied_tweets
    replied_tweets = load_replied_tweets()

    # Load the state
    state = load_state()

    # Initialize the Twitter client
    client = Client('en-US')

    # Try to load saved cookies
    try:
        client.load_cookies(COOKIES_FILE_PATH)
        print("Cookies loaded successfully.")
    except FileNotFoundError:
        print("Cookies file not found. Logging in.")

        # Log in and save cookies
        client.login(auth_info_1=USERNAME, auth_info_2=EMAIL, password=PASSWORD)
        client.save_cookies(COOKIES_FILE_PATH)

    # Set the current user and replied tweets count from the loaded state
    current_user = state["current_user"]
    replied_tweets_count = state["replied_tweets_count"]

    # Main loop
    while True:
        for username in usernames_to_search:
            # Check if the current user is None or if it's a new user
            if current_user is None or username == current_user:
                await reply_to_tweets(client, username)
            else:
                print(f"Skipping user {username} as it's not the current user.")

        # Check if all users' latest 5 tweets have been replied to
        if all(len(replied_tweets.get(username, {})) >= 5 for username in usernames_to_search):
            print("All users' latest 5 tweets have been replied to. Sleeping for 20 minutes.")
            await asyncio.sleep(1200)  # 1200 seconds = 20 minutes
            # Reset the current user and replied tweets count
            current_user = None
            replied_tweets_count = 0
        else:
            # Save the state with the current user and replied tweets count
            save_state(current_user, replied_tweets_count)

if __name__ == "__main__":
    asyncio.run(main())
