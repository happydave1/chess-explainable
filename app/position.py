from __future__ import annotations

import chess


PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 99,
}


class Position:
    """Convenience wrapper for move tagging from one analyzed move."""

    def __init__(self, fen: str, move_uci: str):
        self.board_before = chess.Board(fen)
        self.move = chess.Move.from_uci(move_uci.strip())
        self.pov = self.board_before.turn

        self.board_after = self.board_before.copy(stack=False)
        self._is_legal = self.board_before.is_legal(self.move)
        self._captured_piece_before_move = self._captured_piece_on_before_board()
        if self._is_legal:
            self.board_after.push(self.move)

    def _captured_piece_on_before_board(self) -> chess.Piece | None:
        if self.board_before.is_en_passant(self.move):
            offset = -8 if self.pov == chess.WHITE else 8
            captured_sq = self.move.to_square + offset
            return self.board_before.piece_at(captured_sq)
        return self.board_before.piece_at(self.move.to_square)

    @property
    def moved_piece(self) -> chess.Piece | None:
        return self.board_before.piece_at(self.move.from_square)

    @property
    def moved_piece_type(self) -> int | None:
        piece = self.moved_piece
        return piece.piece_type if piece else None

    @property
    def captured_piece(self) -> chess.Piece | None:
        return self._captured_piece_before_move

    def is_legal(self) -> bool:
        return self._is_legal

    def is_illegal(self) -> bool:
        return not self._is_legal

    def is_capture(self) -> bool:
        return self.board_before.is_capture(self.move)

    def is_en_passant(self) -> bool:
        return self.board_before.is_en_passant(self.move)

    def is_castling(self) -> bool:
        return self.board_before.is_castling(self.move)

    def is_promotion(self) -> bool:
        return self.move.promotion is not None

    def is_underpromotion(self) -> bool:
        return self.move.promotion is not None and self.move.promotion != chess.QUEEN

    def gives_check(self) -> bool:
        return self.board_after.is_check()

    def is_checkmate(self) -> bool:
        return self.board_after.is_checkmate()

    def is_double_check(self) -> bool:
        return len(self.board_after.checkers()) > 1

    def value(self, piece_type: int | None) -> int:
        if piece_type is None:
            return 0
        return PIECE_VALUES.get(piece_type, 0)

    def material_diff(self, board: chess.Board | None = None) -> int:
        """Material from POV perspective (own - opponent, kings ignored)."""
        b = board or self.board_after
        own = 0
        opp = 0
        for square, piece in b.piece_map().items():
            _ = square
            if piece.piece_type == chess.KING:
                continue
            v = self.value(piece.piece_type)
            if piece.color == self.pov:
                own += v
            else:
                opp += v
        return own - opp

    def is_hanging(self, board: chess.Board, square: chess.Square) -> bool:
        piece = board.piece_at(square)
        if piece is None:
            return False
        attackers = board.attackers(not piece.color, square)
        if not attackers:
            return False
        defenders = board.attackers(piece.color, square)
        return len(defenders) == 0
        