from flask import Blueprint, abort, render_template

from .content import (
    INSIGHT_SECTIONS,
    get_featured_insight,
    get_insight,
    get_published_insights,
    get_related_insights,
)

insights_bp = Blueprint(
    "insights",
    __name__,
    url_prefix="/insights",
)


@insights_bp.route("")
def insights():
    featured_section, featured_article = get_featured_insight()

    sections = {
        section: {
            **config,
            "articles": get_published_insights(section),
        }
        for section, config in INSIGHT_SECTIONS.items()
    }

    return render_template(
        "insights/insights.html",
        sections=sections,
        featured_section=featured_section,
        featured_article=featured_article,
    )


@insights_bp.route("/<section>/")
def section_list(section):
    if section not in INSIGHT_SECTIONS:
        abort(404)

    articles = get_published_insights(section)

    return render_template(
        "insights/article_list.html",
        section=section,
        section_config=INSIGHT_SECTIONS[section],
        articles=articles,
    )


@insights_bp.route("/blogs/<slug>/")
def blog_detail(slug):
    return _render_article("blogs", slug)


@insights_bp.route("/market-updates/<slug>/")
def market_update_detail(slug):
    return _render_article("market-updates", slug)


@insights_bp.route("/perspectives/<slug>/")
def perspective_detail(slug):
    return _render_article("perspectives", slug)


def _render_article(section, slug):
    article = get_insight(section, slug)

    if article is None:
        abort(404)

    related_articles = get_related_insights(section, slug)

    return render_template(
        "insights/article_detail.html",
        section=section,
        section_config=INSIGHT_SECTIONS[section],
        article=article,
        related_articles=related_articles,
    )