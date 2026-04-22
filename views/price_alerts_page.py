"""Price Alerts page."""

import streamlit as st

from modules.ui_helpers import gradient_divider, render_fuzzy_suggestions, market_signal_badge
from modules.price_alerts import add_alert, remove_alert, get_alerts
from modules.card_types import get_card_type_options
from modules.trade_analyzer import get_card_market_value
from modules.affiliates import ebay_search_affiliate_url
from tiers import can_access, render_upgrade_prompt


def render():
    st.title("🔔 Price Alerts")
    st.caption("Get notified when cards hit your target price")

    if not can_access("price_alerts"):
        render_upgrade_prompt("Price Alerts", "Set custom price targets and get notified when cards hit your buy/sell point.")
        st.stop()

    # Pick up fuzzy suggestion before widget renders
    _fz_pick = st.session_state.pop("_al_fuzzy_pick", "")
    if _fz_pick:
        st.session_state["al_player"] = _fz_pick

    st.markdown("**Create New Alert**")

    al1, al2, al3 = st.columns(3)
    with al1:
        al_player = st.text_input("Player Name", placeholder="e.g. Jared McCain", key="al_player")
    with al2:
        al_sport = st.selectbox("Sport", ["NBA", "NFL", "MLB", "Pokemon"], key="al_sport")
    with al3:
        al_type_opt = st.selectbox("Card Type", get_card_type_options(), key="al_type")

    # Fuzzy search
    if al_player:
        _sug = render_fuzzy_suggestions(al_player, al_sport, key_prefix="al_fz")
        if _sug:
            st.session_state["_al_fuzzy_pick"] = _sug
            st.rerun()

    # Optional card details
    with st.expander("Describe a specific card (optional)"):
        ad1, ad2, ad3 = st.columns(3)
        with ad1:
            al_year = st.text_input("Year", placeholder="e.g. 2023-24", key="al_year")
        with ad2:
            al_set = st.text_input("Set", placeholder="e.g. Prizm", key="al_set")
        with ad3:
            al_variant = st.text_input("Variant", placeholder="e.g. Silver, Base", key="al_variant")

    # Show current market price to inform the threshold
    _current_price = None
    if al_player:
        from modules.fuzzy_search import has_exact_match
        if has_exact_match(al_player, al_sport):
            _mkt_key = f"_al_mkt_{al_player}_{al_sport}_{al_type_opt}"
            if _mkt_key not in st.session_state:
                with st.spinner("Looking up current price..."):
                    _mkt = get_card_market_value(al_player, al_sport, al_type_opt,
                                                  year=al_year or None, set_name=al_set or None)
                    st.session_state[_mkt_key] = _mkt
            else:
                _mkt = st.session_state[_mkt_key]

            if _mkt and (_mkt.get("avg_sold", 0) > 0 or _mkt.get("avg_active", 0) > 0):
                _current_price = _mkt["avg_sold"] if _mkt["avg_sold"] > 0 else _mkt["avg_active"]
                cm1, cm2, cm3 = st.columns(3)
                cm1.metric("Current Avg Sold", f"${_mkt['avg_sold']:.2f}")
                cm2.metric("Current Avg Active", f"${_mkt['avg_active']:.2f}")
                cm3.markdown(market_signal_badge(_mkt.get("market_signal", "N/A")), unsafe_allow_html=True)

    # Alert threshold
    _default_price = round(_current_price * 0.85, 2) if _current_price else 0.01
    al4, al5, al6 = st.columns(3)
    with al4:
        al_direction = st.selectbox("Alert When", ["Below", "Above"], key="al_dir")
    with al5:
        al_price = st.number_input("Price Threshold ($)", min_value=0.01, value=_default_price, step=1.0, key="al_price")
    with al6:
        al_note = st.text_input("Note (optional)", placeholder="e.g. Buy at dip", key="al_note")

    if _current_price and al_direction == "Below":
        st.caption(f"Alert will fire when avg sold drops below ${al_price:.2f} (currently ${_current_price:.2f})")
    elif _current_price and al_direction == "Above":
        st.caption(f"Alert will fire when avg sold rises above ${al_price:.2f} (currently ${_current_price:.2f})")

    if st.button("Create Alert", type="primary", use_container_width=True, key="al_submit"):
        if al_player and al_price > 0:
            add_alert(al_player, al_sport, al_type_opt, al_direction.lower(), al_price, al_note,
                      year=al_year or None, set_name=al_set or None, variant=al_variant or None)
            st.success(f"Alert created for {al_player} {al_direction.lower()} ${al_price:.2f}")
            st.rerun()
        elif not al_player:
            st.warning("Enter a player name.")

    gradient_divider()

    alerts = get_alerts()

    if not alerts:
        st.info("No alerts set. Create your first alert above!")
    else:
        st.markdown(f"### Active Alerts ({len(alerts)})")

        for alert in alerts:
            # Build card description
            card_desc = f"**{alert['player_name']}** ({alert['sport']})"
            details = []
            if alert.get("year"):
                details.append(alert["year"])
            if alert.get("set_name"):
                details.append(alert["set_name"])
            if alert.get("variant"):
                details.append(alert["variant"])
            elif alert.get("card_type") and alert["card_type"] != "Any":
                details.append(alert["card_type"])
            if details:
                card_desc += f" — {' '.join(details)}"

            ac1, ac2, ac3, ac4, ac5 = st.columns([3, 1.5, 1.5, 1.5, 0.5])
            with ac1:
                st.markdown(card_desc)
            with ac2:
                direction_label = "drops below" if alert["alert_type"] == "below" else "rises above"
                st.write(f"{direction_label} ${alert['threshold_price']:.2f}")
            with ac3:
                if alert.get("last_price"):
                    st.write(f"Last: ${alert['last_price']:.2f}")
                else:
                    st.write("Last: —")
            with ac4:
                if alert.get("triggered"):
                    st.markdown('<span class="alert-triggered">TRIGGERED</span>', unsafe_allow_html=True)
                else:
                    st.markdown('<span class="alert-watching">WATCHING</span>', unsafe_allow_html=True)
            with ac5:
                if st.button("X", key=f"rm_al_{alert['id']}"):
                    remove_alert(alert["id"])
                    st.rerun()

            if alert.get("note"):
                st.caption(f"Note: {alert['note']}")

            # Triggered alert = highest intent moment — show buy link
            if alert.get("triggered"):
                buy_url = ebay_search_affiliate_url(
                    alert["player_name"], alert["sport"], alert.get("card_type", "")
                )
                st.markdown(
                    f'<div style="background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.3);'
                    f'border-radius:8px;padding:8px 14px;margin:4px 0 12px 0;">'
                    f'Your target price was hit. &nbsp;'
                    f'<a href="{buy_url}" target="_blank" class="ebay-btn">Buy Now on eBay</a>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
