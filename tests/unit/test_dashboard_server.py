"""Tests for DashboardServer class (BUG-039)."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.dashboard.web_server import DashboardServer
from src.config import ServerConfig


class TestDashboardServerInit:
    """Test DashboardServer initialization."""

    def test_init_with_all_components(self):
        """Test initialization with all components provided."""
        metrics_collector = MagicMock()
        alert_engine = MagicMock()
        health_reporter = MagicMock()
        store = MagicMock()
        config = ServerConfig()

        server = DashboardServer(
            metrics_collector=metrics_collector,
            alert_engine=alert_engine,
            health_reporter=health_reporter,
            store=store,
            config=config,
        )

        assert server.metrics_collector == metrics_collector
        assert server.alert_engine == alert_engine
        assert server.health_reporter == health_reporter
        assert server.store == store
        assert server.config == config
        assert server.is_running is False

    def test_init_with_minimal_components(self):
        """Test initialization with minimal components."""
        server = DashboardServer()

        assert server.metrics_collector is None
        assert server.alert_engine is None
        assert server.health_reporter is None
        assert server.store is None
        assert server.config is not None  # Should use default config
        assert server.is_running is False

    def test_init_creates_default_config(self):
        """Test that default config is created if not provided."""
        server = DashboardServer()
        assert isinstance(server.config, ServerConfig)


class TestDashboardServerStart:
    """Test DashboardServer start method."""

    @pytest.mark.asyncio
    async def test_start_initializes_components(self):
        """Test that start() initializes all necessary components."""
        server = DashboardServer(config=ServerConfig())

        with patch('src.dashboard.web_server.MemoryRAGServer') as MockRAGServer:
            with patch('src.dashboard.web_server.HTTPServer') as MockHTTPServer:
                with patch('src.dashboard.web_server.threading.Thread') as MockThread:
                    with patch('asyncio.run_coroutine_threadsafe') as mock_run_coroutine:
                        with patch('asyncio.new_event_loop') as mock_new_loop:
                            # Setup mocks
                            mock_rag = AsyncMock()
                            mock_rag.initialize = AsyncMock()
                            MockRAGServer.return_value = mock_rag

                            # Mock event loop
                            mock_loop = MagicMock()
                            mock_new_loop.return_value = mock_loop

                            # Mock future result for initialize()
                            mock_future = MagicMock()
                            mock_future.result = MagicMock(return_value=None)
                            mock_run_coroutine.return_value = mock_future

                            # Start server
                            await server.start(host="localhost", port=8080)

                            # Verify components were initialized
                            assert server.is_running is True
                            assert server.event_loop is not None
                            assert server.loop_thread is not None
                            assert server.rag_server is not None
                            MockRAGServer.assert_called_once()
                            MockHTTPServer.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_with_custom_host_port(self):
        """Test starting server with custom host and port."""
        server = DashboardServer(config=ServerConfig())

        with patch('src.dashboard.web_server.MemoryRAGServer') as MockRAGServer:
            with patch('src.dashboard.web_server.HTTPServer') as MockHTTPServer:
                with patch('src.dashboard.web_server.threading.Thread'):
                    with patch('asyncio.run_coroutine_threadsafe') as mock_run_coroutine:
                        with patch('asyncio.new_event_loop') as mock_new_loop:
                            mock_rag = AsyncMock()
                            mock_rag.initialize = AsyncMock()
                            MockRAGServer.return_value = mock_rag

                            # Mock event loop
                            mock_loop = MagicMock()
                            mock_new_loop.return_value = mock_loop

                            # Mock future result for initialize()
                            mock_future = MagicMock()
                            mock_future.result = MagicMock(return_value=None)
                            mock_run_coroutine.return_value = mock_future

                            await server.start(host="0.0.0.0", port=9000)

                            # Verify HTTPServer was called with correct args
                            MockHTTPServer.assert_called_once()
                            call_args = MockHTTPServer.call_args
                            assert call_args[0][0] == ("0.0.0.0", 9000)

    @pytest.mark.asyncio
    async def test_start_raises_if_already_running(self):
        """Test that start() raises RuntimeError if already running."""
        server = DashboardServer(config=ServerConfig())
        server.is_running = True

        with pytest.raises(RuntimeError, match="already running"):
            await server.start()


class TestDashboardServerStop:
    """Test DashboardServer stop method."""

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self):
        """Test that stop() does nothing if server is not running."""
        server = DashboardServer()
        assert server.is_running is False

        # Should not raise any errors
        await server.stop()

    @pytest.mark.asyncio
    async def test_stop_cleans_up_resources(self):
        """Test that stop() properly cleans up all resources."""
        server = DashboardServer()

        # Mock the components as if server was started
        server.is_running = True

        # Create proper mocks with the methods the code expects
        mock_http_server = MagicMock()
        mock_http_server.shutdown = MagicMock()
        server.server = mock_http_server

        mock_rag_server = MagicMock()
        mock_rag_server.close = AsyncMock()
        server.rag_server = mock_rag_server

        mock_event_loop = MagicMock()
        mock_event_loop.call_soon_threadsafe = MagicMock()
        mock_event_loop.stop = MagicMock()
        server.event_loop = mock_event_loop

        mock_thread = MagicMock()
        mock_thread.join = MagicMock()
        server.loop_thread = mock_thread

        with patch('asyncio.run_coroutine_threadsafe') as mock_run:
            mock_future = MagicMock()
            mock_future.result = MagicMock(return_value=None)
            mock_run.return_value = mock_future

            await server.stop()

            # Verify cleanup
            mock_http_server.shutdown.assert_called_once()
            assert server.is_running is False


class TestDashboardServerIntegration:
    """Integration tests for DashboardServer."""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Integration test - requires full setup")
    async def test_start_stop_lifecycle(self):
        """Test complete start/stop lifecycle."""
        server = DashboardServer(config=ServerConfig())

        # Start server
        await server.start(host="localhost", port=8888)
        assert server.is_running is True

        # Stop server
        await server.stop()
        assert server.is_running is False

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Integration test - requires full setup")
    async def test_server_handles_requests(self):
        """Test that server can handle HTTP requests."""
        server = DashboardServer(config=ServerConfig())

        await server.start(host="localhost", port=8889)

        # TODO: Make HTTP request to server
        # assert response is valid

        await server.stop()
