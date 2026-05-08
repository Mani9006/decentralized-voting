"""
Command-line interface for election management.

Provides commands to create elections, register voters, cast votes,
tally results, and monitor the voting system.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from typing import Any, List, Optional

from src.chain.vote_chain import VoteChain
from src.chain.verification import ChainVerifier
from src.consensus.validators import ConsensusManager
from src.crypto.signatures import SignatureManager
from src.crypto.zkp_simulator import ZKPSimulator
from src.election.manager import ElectionManager
from src.election.types import ElectionConfig, ElectionStatus
from src.identity.anonymizer import VoteAnonymizer
from src.identity.registry import VoterRegistry, VoterStatus
from src.identity.verifier import IdentityVerifier, VerificationLevel
from src.voting.tally import VoteTally
from src.voting.vote import ElectionType, Vote, VoteCaster

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class VotingCLI:
    """Command-line interface for the decentralized voting system."""

    def __init__(self) -> None:
        """Initialize CLI with system components."""
        self.election_manager = ElectionManager()
        self.voter_registry = VoterRegistry()
        self.vote_chain = VoteChain()
        self.consensus_manager = ConsensusManager()
        self.vote_caster = VoteCaster()
        self.vote_tally = VoteTally()
        self.sig_manager = SignatureManager()
        self.anonymizer = VoteAnonymizer()
        self.zkp = ZKPSimulator()
        self.verifier = IdentityVerifier()
        self.chain_verifier = ChainVerifier()

    def create_election(
        self,
        title: str,
        description: str,
        election_type: str,
        options: List[str],
        voting_duration: float = 24.0,
        registration_duration: float = 12.0,
        allow_delegation: bool = False,
        creator_id: str = "",
    ) -> None:
        """
        Create a new election.

        Args:
            title: Election title.
            description: Description.
            election_type: single_choice, ranked_choice, or approval.
            options: Voting options.
            voting_duration: Voting period in hours.
            registration_duration: Registration period in hours.
            allow_delegation: Enable proxy voting.
            creator_id: Creator ID.
        """
        try:
            e_type = ElectionType(election_type)
        except ValueError:
            print(f"Invalid election type: {election_type}")
            print("Valid types: single_choice, ranked_choice, approval")
            return

        config = ElectionConfig(allow_delegation=allow_delegation)

        election = self.election_manager.create_quick_election(
            title=title,
            election_type=e_type,
            options=options,
            voting_duration_hours=voting_duration,
            registration_duration_hours=registration_duration,
            creator_id=creator_id,
        )
        election.config = config

        print(f"Election created: {election.election_id}")
        print(f"  Title: {election.title}")
        print(f"  Type: {election.election_type.value}")
        print(f"  Options: {', '.join(election.options)}")
        print(f"  Registration: {self._format_time(election.timing.registration_start)}")
        print(f"  Voting ends: {self._format_time(election.timing.voting_end)}")
        print(f"  Delegation: {'enabled' if allow_delegation else 'disabled'}")

    def register_voter(
        self,
        identity_proof: str = "anonymous",
        metadata: Optional[str] = None,
    ) -> None:
        """
        Register a new voter.

        Args:
            identity_proof: Identity verification proof.
            metadata: Optional JSON metadata.
        """
        private_key, public_key = self.sig_manager.generate_keypair()

        meta = {}
        if metadata:
            try:
                meta = json.loads(metadata)
            except json.JSONDecodeError:
                print("Invalid metadata JSON")
                return

        try:
            profile = self.voter_registry.register_voter(
                public_key=public_key,
                identity_proof=identity_proof,
                metadata=meta,
            )
            print(f"Voter registered: {profile.voter_id}")
            print(f"  Public key: {public_key[:32]}...")
            print(f"  Status: {profile.status.value}")
            print(f"  (Save your private key securely)")
            print(f"  Private key: {private_key}")
        except ValueError as e:
            print(f"Registration failed: {e}")

    def enroll_voter(self, voter_id: str, election_id: str) -> None:
        """
        Enroll a voter in an election.

        Args:
            voter_id: The voter ID.
            election_id: The election ID.
        """
        election = self.election_manager.get_election(election_id)
        if election is None:
            print(f"Election not found: {election_id}")
            return

        try:
            self.voter_registry.register_for_election(voter_id, election_id)
            self.election_manager.increment_registered_voters(election_id)
            print(f"Voter {voter_id} enrolled in election {election_id}")
        except ValueError as e:
            print(f"Enrollment failed: {e}")

    def set_delegation(
        self, voter_id: str, delegate_id: str, election_id: str
    ) -> None:
        """
        Set a delegation (proxy vote).

        Args:
            voter_id: Original voter ID.
            delegate_id: Delegate voter ID.
            election_id: Election ID.
        """
        try:
            self.voter_registry.set_delegation(voter_id, delegate_id, election_id)
            print(f"Delegation set: {voter_id} -> {delegate_id} for {election_id}")
        except ValueError as e:
            print(f"Delegation failed: {e}")

    def cast_vote(
        self,
        voter_id: str,
        election_id: str,
        choice: str,
        private_key: str,
    ) -> None:
        """
        Cast a vote.

        Args:
            voter_id: Voter ID.
            election_id: Election ID.
            choice: Vote choice (int for single, comma-separated for list).
            private_key: Voter's private key.
        """
        election = self.election_manager.get_election(election_id)
        if election is None:
            print(f"Election not found: {election_id}")
            return

        if not self.voter_registry.is_eligible(voter_id, election_id):
            print("Voter is not eligible to vote")
            return

        parsed_choice = self._parse_choice(choice, election.election_type)
        if parsed_choice is None:
            print("Invalid choice format")
            return

        if not self.vote_caster.validate_vote_choice(
            parsed_choice, election.election_type, election.options
        ):
            print("Invalid choice for this election type")
            return

        anon_id = self.anonymizer.create_anonymous_voter_id(
            voter_id, election_id
        )

        previous_hash = self.vote_chain.get_latest_block().block_hash
        vote = self.vote_caster.create_vote(
            voter_id=anon_id,
            election_id=election_id,
            choice=parsed_choice,
            previous_hash=previous_hash,
        )

        try:
            self.vote_caster.cast_vote(vote, private_key)
        except ValueError as e:
            print(f"Vote casting failed: {e}")
            return

        block = self.vote_chain.add_vote(vote)
        self.voter_registry.mark_voted(voter_id, election_id)
        self.election_manager.increment_cast_votes(election_id)

        print(f"Vote cast successfully!")
        print(f"  Block: #{block.index}")
        print(f"  Hash: {block.block_hash[:32]}...")
        print(f"  Vote hash: {vote.compute_hash()[:32]}...")

    def tally_election(self, election_id: str) -> None:
        """
        Tally votes for an election.

        Args:
            election_id: The election ID.
        """
        election = self.election_manager.get_election(election_id)
        if election is None:
            print(f"Election not found: {election_id}")
            return

        votes = self.vote_chain.get_votes_for_election(election_id)
        if not votes:
            print("No votes cast in this election")
            return

        result = self.vote_tally.tally_votes(
            votes=votes,
            election_type=election.election_type,
            options=election.options,
            election_id=election_id,
        )

        result_hash = result.verification_hash or result.election_id
        finalized = self.vote_tally.finalize_result(result, result_hash)
        self.election_manager.store_result(election_id, finalized)

        print(f"Tally complete for {election_id}")
        print(f"  Total votes: {result.total_votes}")
        print(f"  Winner: {result.winner_name or 'Tie/No winner'}")
        print(f"  Results:")
        for option, count in result.option_counts.items():
            bar = "#" * int(count / max(result.total_votes, 1) * 40)
            print(f"    {option}: {count} {bar}")

    def validate_consensus(self, election_id: str) -> None:
        """
        Run consensus validation on results.

        Args:
            election_id: The election ID.
        """
        result = self.election_manager.get_result(election_id)
        if result is None:
            print("No results available for this election")
            return

        result_hash = result.verification_hash

        validators = self.consensus_manager.get_active_validators()
        if not validators:
            for _ in range(3):
                self.consensus_manager.create_validator()
            validators = self.consensus_manager.get_active_validators()

        print(f"Running consensus with {len(validators)} validators...")

        for validator in validators:
            approved = True
            self.consensus_manager.submit_validation(
                validator_id=validator.validator_id,
                election_id=election_id,
                result_hash=result_hash,
                approved=approved,
            )

        consensus = self.consensus_manager.check_consensus(election_id)
        print(f"Consensus result: {consensus.value}")

        state = self.consensus_manager.get_consensus_state(election_id)
        if state:
            print(f"  Approvals: {state.approval_count}/{len(validators)}")
            print(f"  Ratio: {state.approval_ratio:.2%}")

    def verify_chain(self) -> None:
        """Verify the vote chain integrity."""
        valid = self.vote_chain.verify_chain_integrity()
        print(f"Chain integrity: {'VALID' if valid else 'INVALID'}")
        print(f"  Total blocks: {self.vote_chain.get_chain_length()}")

        stats = self.vote_chain.get_chain_statistics()
        for key, value in stats.items():
            print(f"  {key}: {value}")

    def list_elections(self, status: Optional[str] = None) -> None:
        """
        List all elections.

        Args:
            status: Optional status filter.
        """
        election_status = None
        if status:
            try:
                election_status = ElectionStatus(status)
            except ValueError:
                print(f"Invalid status: {status}")
                return

        elections = self.election_manager.list_elections(election_status)
        if not elections:
            print("No elections found")
            return

        for e in elections:
            print(f"{e.election_id}: {e.title}")
            print(f"  Type: {e.election_type.value}")
            print(f"  Phase: {e.phase.value} | Status: {e.status.value}")
            print(f"  Voters: {e.registered_voters} | Votes: {e.cast_votes}")
            print()

    def election_detail(self, election_id: str) -> None:
        """
        Show election details.

        Args:
            election_id: The election ID.
        """
        stats = self.election_manager.get_election_statistics(election_id)
        print(json.dumps(stats, indent=2, default=str))

    def voter_stats(self) -> None:
        """Show voter statistics."""
        stats = self.voter_registry.get_voter_statistics()
        print(json.dumps(stats, indent=2, default=str))

    def _parse_choice(
        self, choice: str, election_type: ElectionType
    ) -> Optional[Any]:
        """
        Parse a choice string based on election type.

        Args:
            choice: Choice string.
            election_type: Type of election.

        Returns:
            Parsed choice.
        """
        if election_type == ElectionType.SINGLE_CHOICE:
            try:
                return int(choice)
            except ValueError:
                return None
        elif election_type in (ElectionType.APPROVAL, ElectionType.RANKED_CHOICE):
            try:
                parts = [int(x.strip()) for x in choice.split(",")]
                return parts
            except ValueError:
                return None
        return None

    def _format_time(self, timestamp: float) -> str:
        """Format a timestamp for display."""
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))


def main(argv: Optional[List[str]] = None) -> None:
    """
    Main CLI entry point.

    Args:
        argv: Command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Decentralized Voting System CLI"
    )
    subparsers = parser.add_subparsers(dest="command")

    # Create election
    create_parser = subparsers.add_parser("create-election", help="Create an election")
    create_parser.add_argument("--title", required=True)
    create_parser.add_argument("--description", required=True)
    create_parser.add_argument("--type", required=True, choices=["single_choice", "ranked_choice", "approval"])
    create_parser.add_argument("--options", required=True, help="Comma-separated options")
    create_parser.add_argument("--voting-duration", type=float, default=24.0)
    create_parser.add_argument("--registration-duration", type=float, default=12.0)
    create_parser.add_argument("--allow-delegation", action="store_true")

    # Register voter
    register_parser = subparsers.add_parser("register-voter", help="Register a voter")
    register_parser.add_argument("--identity-proof", default="anonymous")
    register_parser.add_argument("--metadata", default=None)

    # Enroll
    enroll_parser = subparsers.add_parser("enroll", help="Enroll voter in election")
    enroll_parser.add_argument("--voter-id", required=True)
    enroll_parser.add_argument("--election-id", required=True)

    # Delegate
    delegate_parser = subparsers.add_parser("delegate", help="Set delegation")
    delegate_parser.add_argument("--voter-id", required=True)
    delegate_parser.add_argument("--delegate-id", required=True)
    delegate_parser.add_argument("--election-id", required=True)

    # Cast vote
    vote_parser = subparsers.add_parser("cast-vote", help="Cast a vote")
    vote_parser.add_argument("--voter-id", required=True)
    vote_parser.add_argument("--election-id", required=True)
    vote_parser.add_argument("--choice", required=True)
    vote_parser.add_argument("--private-key", required=True)

    # Tally
    tally_parser = subparsers.add_parser("tally", help="Tally election")
    tally_parser.add_argument("--election-id", required=True)

    # Consensus
    consensus_parser = subparsers.add_parser("consensus", help="Run consensus")
    consensus_parser.add_argument("--election-id", required=True)

    # Verify chain
    subparsers.add_parser("verify-chain", help="Verify vote chain")

    # List elections
    list_parser = subparsers.add_parser("list-elections", help="List elections")
    list_parser.add_argument("--status", default=None)

    # Election detail
    detail_parser = subparsers.add_parser("election-detail", help="Election details")
    detail_parser.add_argument("--election-id", required=True)

    # Voter stats
    subparsers.add_parser("voter-stats", help="Voter statistics")

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return

    cli = VotingCLI()

    if args.command == "create-election":
        cli.create_election(
            title=args.title,
            description=args.description,
            election_type=args.type,
            options=[o.strip() for o in args.options.split(",")],
            voting_duration=args.voting_duration,
            registration_duration=args.registration_duration,
            allow_delegation=args.allow_delegation,
        )
    elif args.command == "register-voter":
        cli.register_voter(
            identity_proof=args.identity_proof,
            metadata=args.metadata,
        )
    elif args.command == "enroll":
        cli.enroll_voter(args.voter_id, args.election_id)
    elif args.command == "delegate":
        cli.set_delegation(args.voter_id, args.delegate_id, args.election_id)
    elif args.command == "cast-vote":
        cli.cast_vote(args.voter_id, args.election_id, args.choice, args.private_key)
    elif args.command == "tally":
        cli.tally_election(args.election_id)
    elif args.command == "consensus":
        cli.validate_consensus(args.election_id)
    elif args.command == "verify-chain":
        cli.verify_chain()
    elif args.command == "list-elections":
        cli.list_elections(args.status)
    elif args.command == "election-detail":
        cli.election_detail(args.election_id)
    elif args.command == "voter-stats":
        cli.voter_stats()


if __name__ == "__main__":
    main()
