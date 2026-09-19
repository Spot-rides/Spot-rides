"""Pagination that reports page state under ``meta.pagination``.

The paginated response body stays a plain list under ``data``; the counts and
navigation links are stashed on the response for
:class:`core.renderers.EnvelopeJSONRenderer` to merge into ``meta``.
"""

from __future__ import annotations

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class EnvelopePageNumberPagination(PageNumberPagination):
    """``?page=`` / ``?page_size=`` pagination, envelope-aware."""

    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        response = Response(data)
        response.pagination_meta = {
            'page': self.page.number,
            'page_size': self.get_page_size(self.request),
            'total_count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
        }
        return response

    def get_paginated_response_schema(self, schema):
        return schema
