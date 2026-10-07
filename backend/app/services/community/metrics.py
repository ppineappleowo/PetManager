def community_metrics(community):
    values = community.metrics()
    values['reply_coverage'] = round(values['answered_posts']/values['published_posts'],4) if values['published_posts'] else 0
    return values
