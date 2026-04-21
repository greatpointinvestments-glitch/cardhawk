"""Pack Simulator — rip virtual packs, see real prices, buy the hits."""

import streamlit as st

from config.pull_rates import PRODUCTS, FREE_PRODUCTS
from modules.pack_simulator import rip_pack, rip_box, save_rip_result, get_rip_stats
from modules.affiliates import ebay_search_affiliate_url, tcgplayer_search_affiliate_url
from modules.ui_helpers import gradient_divider
from tiers import is_pro, render_upgrade_banner, increment_and_check


def render():
    st.title("Pack Simulator")
    st.caption("Pick a product. Rip a pack. See what you pulled with real market prices.")

    username = st.session_state.get("username")
    _user_is_pro = is_pro()

    # --- Product Picker ---
    st.markdown("### Choose Your Product")

    # Sport filter
    sports = sorted(set(p["sport"] for p in PRODUCTS.values()))
    sport_filter = st.radio("Sport", ["All"] + sports, horizontal=True, key="pack_sport")

    available = {}
    for key, product in PRODUCTS.items():
        if sport_filter != "All" and product["sport"] != sport_filter:
            continue
        if not _user_is_pro and key not in FREE_PRODUCTS:
            continue
        available[key] = product

    if not available:
        if not _user_is_pro:
            render_upgrade_banner("Pack Simulator", "all products unlocked")
        else:
            st.info("No products match your filter.")
        return

    product_key = st.selectbox(
        "Product",
        list(available.keys()),
        key="pack_product",
    )
    product = available[product_key]

    # Product info card
    st.markdown(
        f'<div style="background:linear-gradient(135deg,#1a1f2e,#2d3748);border-radius:12px;'
        f'padding:16px 20px;margin:10px 0;border:1px solid #3b4560;">'
        f'<strong>{product_key}</strong><br>'
        f'<span style="color:#9ca3af;">{product["description"]}</span><br>'
        f'<span style="color:#f59e0b;">{product["cards_per_pack"]} cards/pack &bull; '
        f'${product["pack_price"]:.2f}/pack &bull; '
        f'{product["packs_per_box"]} packs/box</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    gradient_divider()

    # --- Rip Buttons ---
    st.markdown("### Rip It!")
    r1, r2 = st.columns(2)

    with r1:
        rip_label = f"Rip a Pack (${product['pack_price']:.2f})"
        if st.button(rip_label, key="rip_pack", use_container_width=True, type="primary"):
            # Check free tier limit
            if not _user_is_pro and username:
                if not increment_and_check("packs"):
                    st.warning("Free tier: 3 packs/day. Upgrade to Pro for unlimited rips!")
                    return
            st.session_state.last_rip = {
                "type": "pack",
                "product": product_key,
            }
            st.rerun()

    with r2:
        if _user_is_pro:
            box_label = f"Rip a Box (${product['box_price']:.2f})"
            if st.button(box_label, key="rip_box", use_container_width=True):
                st.session_state.last_rip = {
                    "type": "box",
                    "product": product_key,
                }
                st.rerun()
        else:
            st.button(
                f"Rip a Box (PRO)", key="rip_box_locked",
                use_container_width=True, disabled=True,
            )
            st.caption("Box rips are a Pro feature")

    # --- Rip Results ---
    last_rip = st.session_state.get("last_rip")
    if last_rip and last_rip.get("product") == product_key:
        gradient_divider()

        if last_rip["type"] == "pack":
            with st.spinner("Ripping pack..."):
                cards = rip_pack(product_key)
            if cards:
                _render_pack_results(cards, product, username)
        elif last_rip["type"] == "box":
            with st.spinner("Ripping box..."):
                box_result = rip_box(product_key)
            if box_result:
                _render_box_results(box_result, product, username)

    gradient_divider()

    # --- Rip Stats ---
    if username:
        st.markdown("### Your Rip Stats")
        stats = get_rip_stats(username)
        if stats["total_packs"] > 0:
            st1, st2, st3, st4 = st.columns(4)
            st1.metric("Packs Ripped", stats["total_packs"])
            st2.metric("Virtual Spent", f"${stats['total_spent_virtual']:.2f}")
            st3.metric("Total Value", f"${stats['total_value_pulled']:.2f}")
            pl = stats["virtual_pl"]
            st4.metric("Virtual P&L", f"${pl:+.2f}", delta=f"${pl:+.2f}")

            if stats["best_pull"]:
                bp = stats["best_pull"]
                st.markdown(
                    f'Best pull ever: **{bp["player_name"]}** {bp["card_type"]} '
                    f'(${bp["value"]:.2f}) on {bp.get("date", "N/A")}'
                )
        else:
            st.info("Rip your first pack to start tracking stats!")
    else:
        st.info("Log in to save your rip history and stats!")

    if not _user_is_pro:
        render_upgrade_banner("Pack Simulator", "unlimited packs, all products, box rips")


def _render_pack_results(cards: list[dict], product: dict, username: str | None):
    """Render the results of a single pack rip."""
    total_value = sum(c["value"] for c in cards)
    cost = product["pack_price"]
    profit = total_value - cost
    hits = [c for c in cards if c["is_hit"]]

    st.markdown("### Pack Results!")

    pm1, pm2, pm3 = st.columns(3)
    pm1.metric("Pack Value", f"${total_value:.2f}")
    pm2.metric("Pack Cost", f"${cost:.2f}")
    color = "normal" if profit >= 0 else "inverse"
    pm3.metric("Profit/Loss", f"${profit:+.2f}", delta=f"${profit:+.2f}")

    if hits:
        st.success(f"You pulled {len(hits)} hit{'s' if len(hits) > 1 else ''}!")

    for card in cards:
        _render_card_row(card, product["sport"])

    # Save result
    if username:
        save_rip_result(username, product.get("_key", ""), cards, cost)


def _render_card_row(card: dict, sport: str):
    """Render a single card from the pack."""
    is_hit = card["is_hit"]

    # Hit styling
    if is_hit:
        border = "border-left:4px solid #f59e0b;" if card["value"] < 20 else "border-left:4px solid #22c55e;"
        bg = "background:rgba(245,158,11,0.08);" if card["value"] < 20 else "background:rgba(34,197,94,0.1);"
    else:
        border = ""
        bg = ""

    c1, c2, c3, c4 = st.columns([3, 1.5, 1, 1.5])

    with c1:
        hit_tag = ' <span class="pack-hit">HIT</span>' if is_hit else ""
        st.markdown(
            f'<div style="{bg}{border}padding:6px 12px;border-radius:6px;margin:2px 0;">'
            f'<strong>{card["player_name"]}</strong>{hit_tag}<br>'
            f'<span style="color:#9ca3af;font-size:0.9em;">{card["tier_name"]} &bull; {card["card_type"]}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with c2:
        value_color = "#22c55e" if card["value"] >= 10 else "#f59e0b" if card["value"] >= 3 else "#9ca3af"
        st.markdown(
            f'<span style="color:{value_color};font-weight:bold;font-size:1.1em;">'
            f'${card["value"]:.2f}</span>',
            unsafe_allow_html=True,
        )
    with c3:
        # Buy button
        if sport == "Pokemon":
            url = tcgplayer_search_affiliate_url(card["player_name"])
        else:
            url = ebay_search_affiliate_url(card["player_name"], sport, card["card_type"])
        st.markdown(
            f'<a href="{url}" target="_blank" class="ebay-btn" '
            f'style="font-size:0.75em;padding:3px 8px;">Buy</a>',
            unsafe_allow_html=True,
        )
    with c4:
        # Add to collection button
        btn_key = f"add_{card['player_name']}_{card['card_type']}_{card['value']}"
        if st.button("+ Collection", key=btn_key, help="Add to your collection"):
            try:
                from modules.portfolio import add_card
                add_card(
                    player_name=card["player_name"],
                    sport=sport,
                    card_type=card["card_type"],
                    purchase_price=0,
                    purchase_date="",
                    scan_source="pack_sim",
                )
                st.toast(f"Added {card['player_name']} to collection!")
            except Exception:
                st.error("Log in to add cards to your collection")


def _render_box_results(box_result: dict, product: dict, username: str | None):
    """Render box rip results — summary + expandable packs."""
    st.markdown("### Box Results!")

    bm1, bm2, bm3 = st.columns(3)
    bm1.metric("Box Value", f"${box_result['total_value']:.2f}")
    bm2.metric("Box Cost", f"${box_result['box_cost']:.2f}")
    pl = box_result["profit_loss"]
    bm3.metric("Profit/Loss", f"${pl:+.2f}", delta=f"${pl:+.2f}")

    if box_result["best_pull"]:
        bp = box_result["best_pull"]
        st.success(
            f"Best pull: **{bp['player_name']}** {bp['card_type']} (${bp['value']:.2f})"
        )

    # Show each pack in an expander
    for pack in box_result["packs"]:
        hits_in_pack = sum(1 for c in pack["cards"] if c["is_hit"])
        label = f"Pack {pack['pack_number']} — ${pack['pack_value']:.2f}"
        if hits_in_pack:
            label += f" ({hits_in_pack} hit{'s' if hits_in_pack > 1 else ''})"

        with st.expander(label):
            for card in pack["cards"]:
                _render_card_row(card, product["sport"])

    # Save all packs
    if username:
        for pack in box_result["packs"]:
            save_rip_result(username, product.get("_key", ""), pack["cards"], product["pack_price"])
