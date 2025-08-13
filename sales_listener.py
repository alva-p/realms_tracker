# sales_listener.py
import discord
from decimal import Decimal
from query import fetch_recent_sales

def _format_price_ron(value):
    """
    La mayoría de endpoints devuelven realPrice con 18 decimales (wei).
    Si tu endpoint usa otra unidad, ajustá este formateo.
    """
    try:
        ron = Decimal(str(value)) / Decimal(10**18)
        # quitar ceros sobrantes
        ron = ron.normalize()
        return f"{ron} RON"
    except Exception:
        return str(value)

async def notify_sale(channel: discord.abc.Messageable, sale: dict, collection_name: str):
    token = sale["assets"][0]["token"] if sale.get("assets") else {}
    token_id = token.get("tokenIdNum") or token.get("tokenIdStr") or "¿?"
    name = token.get("name") or f"Token #{token_id}"
    image = token.get("image")

    price_str = _format_price_ron(sale.get("realPrice"))
    buyer = sale.get("matcher", "¿?")
    seller = sale.get("maker", "¿?")
    tx = sale.get("txHash", "")

    embed = discord.Embed(
        title=f"Venta en {collection_name}",
        description=f"**{name}** (ID: `{token_id}`)",
        url=f"https://app.roninchain.com/tx/{tx}" if tx else discord.Embed.Empty,
    )
    embed.add_field(name="Precio", value=price_str, inline=True)
    embed.add_field(name="Comprador", value=f"`{buyer}`", inline=False)
    embed.add_field(name="Vendedor", value=f"`{seller}`", inline=False)
    if image:
        embed.set_thumbnail(url=image)
    embed.set_footer(text="Ronin • Notificador de ventas")

    await channel.send(embed=embed)

async def check_sales(
    session,
    channel,
    api_url,
    api_key,
    last_timestamp: int,
    collection_name: str,
    contract_address: str,
    fetch_size: int,
    seen_tx_hashes: set,
):
    """
    1) Pide ventas recientes del contrato.
    2) Se queda solo con las que son posteriores a last_timestamp
       (y también deduplica por txHash en caso de empates de timestamp).
    3) Notifica en orden cronológico y devuelve el último timestamp visto.
    """
    sales = await fetch_recent_sales(session, api_url, api_key, contract_address, size=fetch_size)
    # Filtrar nuevas (timestamp > last_timestamp) o iguales pero tx no visto
    new_sales = []
    for s in sales:
        ts = int(s.get("timestamp", 0))
        tx = s.get("txHash")
        if ts > last_timestamp or (ts == last_timestamp and tx and tx not in seen_tx_hashes):
            new_sales.append(s)

    if not new_sales:
        return last_timestamp

    # Ordenar para notificar en orden
    new_sales.sort(key=lambda x: (int(x.get("timestamp", 0)), x.get("txHash") or ""))

    for s in new_sales:
        await notify_sale(channel, s, collection_name)
        tx = s.get("txHash")
        if tx:
            seen_tx_hashes.add(tx)
            # Limpiar set si crece mucho
            if len(seen_tx_hashes) > 2000:
                # descartar arbitrariamente algunos para no crecer sin límite
                for _ in range(len(seen_tx_hashes) - 1500):
                    seen_tx_hashes.pop()

    return max(int(s.get("timestamp", 0)) for s in new_sales)
