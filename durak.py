import random

RANKS = ['6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
SUITS = ['♠', '♥', '♦', '♣']  # spades, hearts, diamonds, clubs
RANK_VALUES = {r: i for i, r in enumerate(RANKS)}


class Card:
    """Represents a single playing card."""

    def __init__(self, suit: str, rank: str):
        self.suit = suit
        self.rank = rank

    def __lt__(self, other):
        return RANK_VALUES[self.rank] < RANK_VALUES[other.rank]

    def __str__(self):
        return f"{self.rank}{self.suit}"

    def beats(self, other: 'Card', trump: str) -> bool:
        """Return True if this card beats ``other`` considering ``trump`` suit."""
        if self.suit == other.suit:
            return RANK_VALUES[self.rank] > RANK_VALUES[other.rank]
        if self.suit == trump and other.suit != trump:
            return True
        return False


class Deck:
    """Standard 36 card deck used in Durak."""

    def __init__(self):
        self.cards = [Card(s, r) for s in SUITS for r in RANKS]
        random.shuffle(self.cards)

    def draw(self) -> Card | None:
        if self.cards:
            return self.cards.pop(0)
        return None

    def __len__(self):
        return len(self.cards)


class Player:
    """Represents a single player."""

    def __init__(self, name: str):
        self.name = name
        self.hand: list[Card] = []

    def draw_to_six(self, deck: Deck):
        """Draw cards from deck until hand has six or deck empty."""
        while len(self.hand) < 6:
            card = deck.draw()
            if card:
                self.hand.append(card)
            else:
                break

    def remove_card(self, card: Card):
        self.hand.remove(card)

    def lowest_trump(self, trump: str) -> Card | None:
        trumps = [c for c in self.hand if c.suit == trump]
        return min(trumps, default=None)

    def has_rank(self, rank: str) -> bool:
        return any(c.rank == rank for c in self.hand)

    def __str__(self):
        return self.name


class DurakGame:
    """Full rules Durak card game for multiple players.

    This engine is text based and uses very naive AI for the players.  The
    purpose is to demonstrate the rule implementation rather than to provide a
    strong computer opponent."""

    def __init__(self, player_names: list[str]):
        if not 2 <= len(player_names) <= 6:
            raise ValueError("Durak typically supports 2-6 players")
        self.players = [Player(n) for n in player_names]
        self.deck = Deck()
        self.discard: list[Card] = []

        # Reveal bottom card to determine trump
        self.trump = self.deck.cards[-1].suit

        # Deal six cards to each player
        for p in self.players:
            p.draw_to_six(self.deck)

        # Determine first attacker: player with lowest trump
        lowest_trump = None
        attacker = 0
        for i, p in enumerate(self.players):
            lt = p.lowest_trump(self.trump)
            if lt and (lowest_trump is None or lt < lowest_trump):
                lowest_trump = lt
                attacker = i
        self.attacker_index = attacker
        self.defender_index = (attacker + 1) % len(self.players)

    # ---------------------------------------------------------------
    # Helper utilities
    def next_player(self, index: int) -> int:
        return (index + 1) % len(self.players)

    def active_players(self) -> list[int]:
        """Return indices of players who still hold cards."""
        return [i for i, p in enumerate(self.players) if p.hand]

    # ---------------------------------------------------------------
    def play(self):
        """Run the game loop until only one player has cards left."""
        round_no = 1
        while len(self.active_players()) > 1:
            print(f"\n--- Round {round_no} ---")
            self.play_round()
            round_no += 1
        loser = self.players[self.active_players()[0]] if self.active_players() else None
        if loser:
            print(f"\n{loser} is the durak!")
        else:
            print("\nEveryone discarded their cards. No durak.")

    def play_round(self):
        """Play a single attack/defense round."""
        attacker = self.attacker_index
        defender = self.defender_index
        table: list[tuple[Card, Card | None]] = []  # (attack, defense)
        passed_attackers: set[int] = set()

        def ranks_on_table() -> set[str]:
            ranks = {a.rank for a, _ in table}
            ranks.update(d.rank for _, d in table if d)
            return ranks

        # Maximum number of attack cards is limited by defender's hand size and
        # by the traditional cap of six cards on the table.
        def attack_limit() -> int:
            return min(6, len(self.players[defender].hand))

        current = attacker
        defender_took = False

        while True:
            if current == defender:
                # Defender's turn: try to cover exposed attacks
                uncovered = [i for i, pair in enumerate(table) if pair[1] is None]
                if not uncovered:
                    # If there are no uncovered cards and every attacker has
                    # passed we can end the round and discard
                    if len(passed_attackers) == len(self.players) - 1:
                        print("Defender succeeded. Discarding table.")
                        self.discard.extend([c for pair in table for c in pair if c])
                        attacker = defender  # Defender becomes new attacker
                        defender = self.next_player(defender)
                        break
                    else:
                        # allow attackers opportunity to add more
                        current = self.next_player(current)
                        continue

                card_index = uncovered[0]
                attack_card = table[card_index][0]
                has_defended = any(pair[1] is not None for pair in table)
                action, card = self.choose_defense(
                    self.players[defender], attack_card, allow_transfer=not has_defended
                )
                if action == "defend":
                    print(f"{self.players[defender]} defends {attack_card} with {card}")
                    table[card_index] = (attack_card, card)
                    self.players[defender].remove_card(card)
                elif action == "transfer":
                    new_def = self.next_player(defender)
                    # Transfer is only legal if new defender can take all cards
                    if len(table) + 1 > min(6, len(self.players[new_def].hand)):
                        print(
                            f"{self.players[defender]} tries to transfer but new defender has too few cards"
                        )
                        defender_took = True
                        print(
                            f"{self.players[defender]} takes the table instead"
                        )
                        for a, d in table:
                            if a:
                                self.players[defender].hand.append(a)
                            if d:
                                self.players[defender].hand.append(d)
                        attacker = self.next_player(defender)
                        defender = self.next_player(attacker)
                        break
                    print(f"{self.players[defender]} transfers {attack_card} with {card}")
                    self.players[defender].remove_card(card)
                    table.append((card, None))
                    defender = new_def
                    passed_attackers.discard(defender)
                    current = defender
                else:
                    # Defender surrenders and takes all cards
                    defender_took = True
                    print(
                        f"{self.players[defender]} cannot defend {attack_card} and takes the table"
                    )
                    for a, d in table:
                        if a:
                            self.players[defender].hand.append(a)
                        if d:
                            self.players[defender].hand.append(d)
                    attacker = self.next_player(defender)
                    defender = self.next_player(attacker)
                    break
            else:
                # Attackers try to add cards
                if len(table) >= attack_limit():
                    passed_attackers.add(current)
                    current = self.next_player(current)
                    continue
                playable = self.attack_options(self.players[current], ranks_on_table())
                if playable:
                    card = playable[0]
                    self.players[current].remove_card(card)
                    table.append((card, None))
                    print(f"{self.players[current]} attacks with {card}")
                    passed_attackers.discard(current)
                else:
                    print(f"{self.players[current]} passes")
                    passed_attackers.add(current)
                current = self.next_player(current)
            # Loop continues until conditions satisfied

        # After round draw cards starting from the new attacker and proceeding
        # clockwise.  Everyone draws up to six cards if possible.
        draw_order = []
        i = attacker
        while True:
            draw_order.append(i)
            i = self.next_player(i)
            if i == attacker:
                break
        for idx in draw_order:
            self.players[idx].draw_to_six(self.deck)

        self.attacker_index = attacker
        self.defender_index = defender

    # ---------------------------------------------------------------
    def attack_options(self, player: Player, allowed_ranks: set[str]):
        """Return list of attack cards ``player`` may use.

        When ``allowed_ranks`` is empty the attack starts and any card may be
        used.  Otherwise only cards whose rank matches a card already on the
        table are legal, implementing the multi-card attack rule."""

        if not allowed_ranks:
            return sorted(player.hand, key=lambda c: RANK_VALUES[c.rank])
        return sorted([c for c in player.hand if c.rank in allowed_ranks], key=lambda c: RANK_VALUES[c.rank])

    def choose_defense(
        self, player: Player, attack_card: Card, allow_transfer: bool
    ) -> tuple[str, Card | None]:
        """Determine how ``player`` reacts to ``attack_card``.

        Returns a tuple ``(action, card)`` where ``action`` is one of:

        - ``'defend'`` – use ``card`` to beat the attack card.
        - ``'transfer'`` – use ``card`` to pass the attack to the next player.
        - ``'take'`` – surrender and pick up the table.

        ``allow_transfer`` is False once the defender has already beaten any
        card during the current round, enforcing the rule that a transfer can
        only happen as the first response."""

        options = [c for c in player.hand if c.beats(attack_card, self.trump)]

        if options:
            # With a small probability the AI voluntarily surrenders even though
            # a defense is possible, modelling the "give up" option that human
            # players have in Durak.
            if random.random() < 0.05:
                return ("take", None)
            card = min(options, key=lambda c: RANK_VALUES[c.rank])
            return ("defend", card)

        if allow_transfer:
            transfer_cards = [c for c in player.hand if c.rank == attack_card.rank]
            if transfer_cards:
                card = min(transfer_cards, key=lambda c: RANK_VALUES[c.rank])
                return ("transfer", card)

        return ("take", None)


if __name__ == "__main__":
    names = ["Alice", "Bob", "Charlie"]
    game = DurakGame(names)
    game.play()
