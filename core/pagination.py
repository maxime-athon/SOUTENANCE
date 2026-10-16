from urllib.parse import urlencode


def build_pagination(request, page_obj, page_param='page', tab=None):
    """Build compact pagination links while preserving the active filters."""
    if not page_obj or not page_obj.paginator.num_pages:
        return None

    params = request.GET.copy()
    if tab:
        params['tab'] = tab

    def page_url(number):
        page_params = params.copy()
        page_params[page_param] = number
        return f'{request.path}?{urlencode(page_params, doseq=True)}'

    items = []
    for value in page_obj.paginator.get_elided_page_range(
        number=page_obj.number, on_each_side=2, on_ends=1
    ):
        if isinstance(value, int):
            items.append({
                'number': value,
                'url': page_url(value),
                'current': value == page_obj.number,
            })
        else:
            items.append({'ellipsis': True})

    return {
        'items': items,
        'previous_url': page_url(page_obj.previous_page_number()) if page_obj.has_previous() else None,
        'next_url': page_url(page_obj.next_page_number()) if page_obj.has_next() else None,
        'first': page_obj.start_index(),
        'last': page_obj.end_index(),
        'total': page_obj.paginator.count,
    }
