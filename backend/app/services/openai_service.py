"""多模型兼容服务 facade。

OpenAIService 保留原类名和外部 API；底层模型调用在 ModelGatewayService，
业务生成逻辑按领域拆分到 services/generation/*.py。
"""
from .fallback_generation import FallbackGenerationMixin
from .model_gateway_service import ModelGatewayService
from .generation.analysis import AnalysisGenerationMixin
from .generation.content import ContentGenerationMixin
from .generation.core import GenerationCoreMixin
from .generation.document_blocks import DocumentBlocksGenerationMixin
from .generation.outline import OutlineGenerationMixin
from .generation.reference_profile import ReferenceProfileGenerationMixin
from .generation.review import ReviewGenerationMixin


class OpenAIService(
    AnalysisGenerationMixin,
    ReferenceProfileGenerationMixin,
    DocumentBlocksGenerationMixin,
    ReviewGenerationMixin,
    ContentGenerationMixin,
    OutlineGenerationMixin,
    GenerationCoreMixin,
    ModelGatewayService,
    FallbackGenerationMixin,
):
    """Bid-document business generation facade with stable public API."""

    pass
