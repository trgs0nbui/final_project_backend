from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response


class CustomPageNumberPagination(PageNumberPagination):
    """
    Phân trang tùy chỉnh cho toàn bộ API danh sách.

    - Mặc định 20 bản ghi mỗi trang.
    - Cho phép client chỉ định page_size qua query param `page_size`.
    - Giới hạn tối đa 100 bản ghi mỗi trang; trả về HTTP 400 nếu vượt quá.
    - Response format: { count, next, previous, results }
    """

    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_page_size(self, request):
        """
        Trả về page_size từ request.
        Raise ValidationError (HTTP 400) nếu page_size > 100.
        """
        page_size_param = request.query_params.get(self.page_size_query_param)

        if page_size_param is not None:
            try:
                page_size = int(page_size_param)
            except (ValueError, TypeError):
                # Để DRF xử lý giá trị không phải số theo cách mặc định
                return super().get_page_size(request)

            if page_size > self.max_page_size:
                raise ValidationError(
                    {
                        'page_size': (
                            f'page_size không được vượt quá {self.max_page_size}. '
                            f'Giá trị nhận được: {page_size}.'
                        )
                    }
                )

        return super().get_page_size(request)

    def get_paginated_response(self, data):
        """
        Trả về response với format chuẩn:
        { count, next, previous, results }
        """
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
        })

    def get_paginated_response_schema(self, schema):
        """Schema cho drf-spectacular / OpenAPI documentation."""
        return {
            'type': 'object',
            'properties': {
                'count': {
                    'type': 'integer',
                    'description': 'Tổng số bản ghi.',
                },
                'next': {
                    'type': 'string',
                    'nullable': True,
                    'description': 'URL trang tiếp theo hoặc null.',
                },
                'previous': {
                    'type': 'string',
                    'nullable': True,
                    'description': 'URL trang trước hoặc null.',
                },
                'results': schema,
            },
        }
