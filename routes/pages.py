"""Page rendering routes"""
from flask import Blueprint, render_template

pages_bp = Blueprint('pages', __name__)

@pages_bp.route('/')
def index():
    """Render the main customer-facing page"""
    return render_template('index.html')

@pages_bp.route('/market/<int:market_id>')
def market_detail_page(market_id):
    """Render individual market detail page"""
    return render_template('market_detail.html', market_id=market_id)

@pages_bp.route('/my-bets')
def my_bets_page():
    """Render the user's bets page"""
    return render_template('my_bets.html')

@pages_bp.route('/resolved')
def resolved_markets_page():
    """Render the resolved markets page"""
    return render_template('resolved_markets.html')


