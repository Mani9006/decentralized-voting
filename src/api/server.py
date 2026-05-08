"""
Election monitoring dashboard data API.

Provides a HTTP API for querying election data, results, and statistics
for use in monitoring dashboards and external integrations.
"""

from __future__ import annotations

import json
import logging
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List, Optional

from src.chain.vote_chain import VoteChain
from src.consensus.validators import ConsensusManager
from src.election.manager import ElectionManager
from src.identity.registry import VoterRegistry

logger = logging.getLogger(__name__)


class DashboardDataAPI:
    """
    API for election monitoring dashboard data.

    Aggregates data from all system components and exposes it
    via a simple HTTP API for dashboard consumption.
    """

    def __init__(
        self,
        election_manager: Optional[ElectionManager] = None,
        voter_registry: Optional[VoterRegistry] = None,
        vote_chain: Optional[VoteChain] = None,
        consensus_manager: Optional[ConsensusManager] = None,
    ) -> None:
        """
        Initialize the dashboard API.

        Args:
            election_manager: ElectionManager instance.
            voter_registry: VoterRegistry instance.
            vote_chain: VoteChain instance.
            consensus_manager: ConsensusManager instance.
        """
        self.election_manager = election_manager or ElectionManager()
        self.voter_registry = voter_registry or VoterRegistry()
        self.vote_chain = vote_chain or VoteChain()
        self.consensus_manager = consensus_manager or ConsensusManager()
        logger.info("DashboardDataAPI initialized")

    def get_dashboard_overview(self) -> Dict[str, Any]:
        """
        Get overview data for the dashboard.

        Returns:
            Dictionary with system-wide statistics.
        """
        elections = self.election_manager.list_elections()
        chain_stats = self.vote_chain.get_chain_statistics()
        voter_stats = self.voter_registry.get_voter_statistics()
        consensus_stats = self.consensus_manager.get_validator_statistics()

        return {
            "timestamp": time.time(),
            "summary": {
                "total_elections": len(elections),
                "active_elections": len(
                    [e for e in elections if str(e.status) == "ElectionStatus.ACTIVE"]
                ),
                "completed_elections": len(
                    [e for e in elections if str(e.status) == "ElectionStatus.COMPLETED"]
                ),
                "total_votes": chain_stats.get("total_votes", 0),
                "total_voters": voter_stats.get("total_voters", 0),
                "total_validators": consensus_stats.get("total_validators", 0),
            },
            "elections": [e.to_dict() for e in elections],
            "chain": chain_stats,
            "voters": voter_stats,
            "consensus": consensus_stats,
        }

    def get_election_detail(self, election_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed data for a specific election.

        Args:
            election_id: The election identifier.

        Returns:
            Detailed election data, or None.
        """
        election = self.election_manager.get_election(election_id)
        if election is None:
            return None

        result = self.election_manager.get_result(election_id)
        consensus = self.consensus_manager.get_consensus_state(election_id)
        votes = self.vote_chain.get_votes_for_election(election_id)
        registered = self.voter_registry.get_registered_voters(election_id)

        return {
            "election": election.to_dict(),
            "result": result.to_dict() if result else None,
            "consensus": consensus.to_dict() if consensus else None,
            "votes": [v.to_dict() for v in votes],
            "registered_voters": registered,
            "total_registered": len(registered),
            "total_cast": len(votes),
        }

    def get_election_results(self, election_id: str) -> Optional[Dict[str, Any]]:
        """
        Get results for an election.

        Args:
            election_id: The election identifier.

        Returns:
            Result data, or None.
        """
        election = self.election_manager.get_election(election_id)
        result = self.election_manager.get_result(election_id)
        consensus = self.consensus_manager.get_consensus_state(election_id)

        if election is None:
            return None

        return {
            "election_id": election_id,
            "title": election.title,
            "election_type": election.election_type.value,
            "phase": election.phase.value,
            "options": election.options,
            "result": result.to_dict() if result else None,
            "consensus_reached": (
                consensus.is_approved() if consensus else False
            ),
            "total_votes": election.cast_votes,
            "registered_voters": election.registered_voters,
            "turnout": (
                (election.cast_votes / election.registered_voters * 100)
                if election.registered_voters > 0
                else 0
            ),
        }

    def get_live_elections(self) -> List[Dict[str, Any]]:
        """
        Get currently active elections.

        Returns:
            List of active election summaries.
        """
        elections = self.election_manager.list_elections()
        live = []
        for e in elections:
            self.election_manager.update_election_status(e.election_id)
            if e.phase.value in ("voting", "registration"):
                live.append({
                    "election_id": e.election_id,
                    "title": e.title,
                    "phase": e.phase.value,
                    "type": e.election_type.value,
                    "registered": e.registered_voters,
                    "cast": e.cast_votes,
                    "time_remaining": e.timing.time_until_voting_end,
                    "options": e.options,
                })
        return live

    def get_chain_status(self) -> Dict[str, Any]:
        """
        Get vote chain status.

        Returns:
            Chain statistics.
        """
        return self.vote_chain.get_chain_statistics()

    def get_voter_statistics(self) -> Dict[str, Any]:
        """
        Get voter statistics.

        Returns:
            Voter data.
        """
        return self.voter_registry.get_voter_statistics()

    def get_consensus_status(self) -> Dict[str, Any]:
        """
        Get consensus validation status.

        Returns:
            Consensus statistics.
        """
        return self.consensus_manager.get_validator_statistics()

    def to_json(self, data: Any) -> str:
        """
        Serialize data to JSON.

        Args:
            data: Data to serialize.

        Returns:
            JSON string.
        """
        return json.dumps(data, indent=2, default=str)


class DashboardHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the dashboard API."""

    api: Optional[DashboardDataAPI] = None

    def do_GET(self) -> None:
        """Handle GET requests."""
        if self.api is None:
            self._send_error(500, "API not initialized")
            return

        path = self.path

        if path == "/":
            self._send_json(self.api.get_dashboard_overview())
        elif path == "/elections":
            elections = self.api.election_manager.list_elections()
            self._send_json([e.to_dict() for e in elections])
        elif path == "/live":
            self._send_json(self.api.get_live_elections())
        elif path == "/chain":
            self._send_json(self.api.get_chain_status())
        elif path == "/voters":
            self._send_json(self.api.get_voter_statistics())
        elif path == "/consensus":
            self._send_json(self.api.get_consensus_status())
        elif path.startswith("/election/"):
            election_id = path.split("/")[2]
            if path.endswith("/results"):
                result = self.api.get_election_results(election_id)
                if result:
                    self._send_json(result)
                else:
                    self._send_error(404, "Election not found")
            else:
                detail = self.api.get_election_detail(election_id)
                if detail:
                    self._send_json(detail)
                else:
                    self._send_error(404, "Election not found")
        else:
            self._send_error(404, "Not found")

    def do_OPTIONS(self) -> None:
        """Handle OPTIONS requests for CORS."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        """Override to use logger."""
        logger.info(format % args)

    def _send_json(self, data: Any) -> None:
        """Send JSON response."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2, default=str).encode())

    def _send_error(self, code: int, message: str) -> None:
        """Send error response."""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(
            json.dumps({"error": message}).encode()
        )


def start_api_server(
    host: str = "localhost",
    port: int = 8000,
    election_manager: Optional[ElectionManager] = None,
    voter_registry: Optional[VoterRegistry] = None,
    vote_chain: Optional[VoteChain] = None,
    consensus_manager: Optional[ConsensusManager] = None,
) -> HTTPServer:
    """
    Start the dashboard API server.

    Args:
        host: Host to bind to.
        port: Port to listen on.
        election_manager: ElectionManager instance.
        voter_registry: VoterRegistry instance.
        vote_chain: VoteChain instance.
        consensus_manager: ConsensusManager instance.

    Returns:
        The running HTTPServer.
    """
    api = DashboardDataAPI(
        election_manager=election_manager,
        voter_registry=voter_registry,
        vote_chain=vote_chain,
        consensus_manager=consensus_manager,
    )
    DashboardHTTPHandler.api = api

    server = HTTPServer((host, port), DashboardHTTPHandler)
    logger.info("Dashboard API server started on %s:%d", host, port)
    return server


def run_server(
    host: str = "localhost",
    port: int = 8000,
    **kwargs: Any,
) -> None:
    """
    Run the API server (blocking).

    Args:
        host: Host to bind to.
        port: Port to listen on.
        **kwargs: Component instances to inject.
    """
    server = start_api_server(host=host, port=port, **kwargs)
    try:
        logger.info("Server running at http://%s:%d", host, port)
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server shutting down")
        server.shutdown()
