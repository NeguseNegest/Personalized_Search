# Personalised_Search

## SETUP:
Start by running the following in the terminal to set up elastic search and kibana. Make sure to have docker installed and opened: 

´´´curl -fsSL https://elastic.co/start-local | sh´´´

Export the password, url and api_key  and connect to the index.

´´´cd elastic-start-local
source .env
export ES_LOCAL_URL
export ES_LOCAL_API_KEY
export ES_LOCAL_PASSWORD´´´

Run connect.py and see that everything works.