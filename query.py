# query.py
import aiohttp

async def fetch_recent_sales(session, api_url, api_key, contract_address, size=10, from_=0):
    query = """
    query RecentSales($tokenAddress: String!, $from: Int!, $size: Int!) {
      recentlySolds(from: $from, size: $size, tokenAddress: $tokenAddress) {
        results {
          assets {
            token {
              __typename
              ... on Erc1155 {
                tokenIdNum: tokenId
                name
                image
              }
              ... on Erc721 {
                tokenIdStr: tokenId
                name
                image
              }
            }
          }
          maker
          matcher
          realPrice
          timestamp
          txHash
        }
      }
    }
    """
    variables = {"tokenAddress": contract_address, "from": from_, "size": size}
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["x-api-key"] = api_key

    async with session.post(api_url, json={"query": query, "variables": variables}, headers=headers) as r:
        if r.status != 200:
            body = await r.text()
            raise RuntimeError(f"GraphQL HTTP {r.status}: {body}")
        data = await r.json()

    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")
    return data["data"]["recentlySolds"]["results"]
