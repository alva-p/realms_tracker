Realms Tracker
A Python-based bot for tracking NFT sales and events in the Realms ecosystem, focusing on Kojins and Mounts collections (with plans to expand to more NFTs from the project). It uses asynchronous HTTP requests to poll Ronin and OpenSea APIs at configurable intervals, sending notifications to a Discord channel. The bot is designed to run continuously and is hosted on Google Cloud Platform for 24/7 availability.
Project Overview
This bot monitors NFT marketplaces for the Realms project on the Ronin chain. It fetches data from Ronin and OpenSea APIs to detect new sales or events, processes the information, and posts updates to a specified Discord channel. The development involved using the GraphQL Playground of Ronin for interacting with collections and testing queries. The bot is built with Python for simplicity and efficiency, leveraging libraries like discord.py for Discord integration and aiohttp for asynchronous API calls. It is deployed on a free-tier Google Cloud VM (e2-micro instance) to ensure constant operation without costs, as long as it stays within GCP's free tier limits (e.g., low CPU usage and <1 GB monthly egress network traffic).
Key features:

Polls APIs at a configurable interval (default: 120 seconds to stay within free tier limits).
Tracks up to 100 events per fetch for efficiency.
Stores last sales data in JSON to avoid duplicates.
Sends formatted notifications to Discord.

Files and Structure
The repository includes the following files, each serving a specific purpose:

bot.py: The main script that initializes the Discord bot, loads environment variables from .env, and runs the polling loop. It uses discord.py for bot commands and events, aiohttp for API requests, and imports check_sales from sales_listener.py to process data. This file handles the core logic of connecting to Discord, fetching NFT events, and sending notifications.

sales_listener.py: Contains the check_sales function, which handles the logic for querying Ronin and OpenSea APIs using GraphQL and REST endpoints. It processes the fetched data (e.g., sales events), compares against stored last sales to detect new ones, and formats messages for Discord. This file is responsible for the NFT tracking core.

last_sales.json: A JSON file that stores the most recent sales data to prevent duplicate notifications. It is updated after each successful poll, ensuring the bot only alerts on new events.

.env: Configuration file for sensitive variables like Discord token (DISCORD_TOKEN), API keys (API_KEY, OPENSEA_API_KEY), channel ID (CHANNEL_ID), API URLs (RONIN_API_URL), polling interval (POLL_INTERVAL_SECONDS), and fetch size (FETCH_SIZE). This file is not committed to the repository (ignored via .gitignore) for security.

.gitignore: Excludes sensitive or temporary files from version control, such as .env, log files (*.log), the virtual environment (.venv/), Python cache (__pycache__/), and last_sales.json.

README.md: This documentation file (you're reading it now).


Example Notification
The bot sends notifications to the specified Discord channel when new sales are detected. Here's an example of how a sale notification might look in Discord for a Kojin NFT (formatted as an embed message for better readability):
(The image shows a Discord message from "Realms Tracker" notifying a Kojin Genesis sale for 300,000 RON, with buyer and seller addresses, and a link to Ronin + Sales notifier.)
Setup and Deployment

Local Setup:

Clone the repository: git clone https://github.com/alva-p/realms_tracker.
Create a virtual environment: python3 -m venv .venv and activate it.
Install dependencies: pip3 install -r requirements.txt (create requirements.txt with libraries like discord.py, aiohttp, python-dotenv if not present).
Create .env with your variables (e.g., DISCORD_TOKEN, CHANNEL_ID from Discord, API keys from Ronin/OpenSea).


Running Locally:

Execute python3 bot.py.
The bot connects to Discord and starts polling APIs every 120 seconds.


Deployment on Google Cloud (24/7 Hosting):

Create a free e2-micro VM in GCP (e.g., Ubuntu 22.04 LTS, zone us-central1-a).
Clone the repo, install Python and dependencies.
Use PM2 (Node.js process manager) to run the bot continuously: pm2 start bot.py --interpreter=python3.
This setup stays within GCP's free tier (1 e2-micro VM/month, <1 GB egress network/month) for low-traffic bots like this.



Realms Project Links

Official Realms website: roninrealms.com and realms.game.
NFT Collections Tracked:
Kojins: marketplace.roninchain.com/collections/kojin.
Mounts: marketplace.roninchain.com/collections/realmsmounts.



Future Improvements

Add support for more Realms NFTs.
Optimize polling for lower resource usage.
Integrate additional marketplaces or alerts.

Contributions are welcome! If you have suggestions or issues, open a pull request or issue on GitHub.