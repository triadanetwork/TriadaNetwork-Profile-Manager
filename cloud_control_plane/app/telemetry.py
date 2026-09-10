import logging

from .config import settings

LOGGER = logging.getLogger("triada.telemetry")


def configure_optional_telemetry(app) -> None:
    s = settings()
    if s.sentry_dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.fastapi import FastApiIntegration

            sentry_sdk.init(
                dsn=s.sentry_dsn,
                integrations=[FastApiIntegration()],
                traces_sample_rate=s.sentry_traces_sample_rate,
                environment=s.environment,
                send_default_pii=False,
            )
            LOGGER.info("sentry.enabled")
        except ImportError:
            LOGGER.warning("sentry.configured_but_package_missing")

    if not s.otel_enabled:
        return
    if not s.otel_exporter_otlp_endpoint:
        LOGGER.warning("otel.enabled_without_endpoint")
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({"service.name": s.otel_service_name, "deployment.environment": s.environment})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=s.otel_exporter_otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app, excluded_urls="/health/live,/health/ready,/metrics")
        SQLAlchemyInstrumentor().instrument()
        LOGGER.info("otel.enabled")
    except ImportError:
        LOGGER.warning("otel.enabled_but_packages_missing")
