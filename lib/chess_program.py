RANKS, FILES = "87654321", "abcdefgh"
STANDARD_BACK_RANK_ORDER = ['rook', 'knight', 'bishop', 'queen', 'king', 'bishop', 'knight', 'rook']

def sign(x):
    if x < 0: return -1
    elif x > 0: return +1
    else: return 0

def get_empty_board():
    return { f + r: None for r in RANKS for f in FILES }

def get_standard_starting_board():
    back_rank = dict(zip(FILES, STANDARD_BACK_RANK_ORDER))
    return {
        f + r: (
            'black' if r in "87" else 'white',
            back_rank.get(f) if r in "18" else 'pawn'
        ) if r in "8721" else None
        for r in RANKS
        for f in FILES
    }

class ChessProgram:
    def __init__(self):
        self.board = get_empty_board()
        self.input_prefix = '$ '  # Should always end in a space
        self.input_suffix = '\n'
        self.output_prefix = '> ' # Should always end in a space
        self.output_suffix = '\n'
        self.active_color = 'white'
        self.lines = []
        self.line_handlers = []

    def on_line(self, line_handler):
        self.line_handlers.append(line_handler)

    def add_line(self, line):
        self.lines.append(line)
        for line_handler in self.line_handlers:
            line_handler(line)

    def succeed(self, content = None):
        if content is None:
            line = self.output_prefix + 'ok' + self.output_suffix
        else:
            line = self.output_prefix + content + self.output_suffix
        self.add_line(line)

    def handle_command(self, command):
        # Anything from # onwards is a commend and therefore ignored
        command = command.split('#')[0].strip()
        line = self.input_prefix + command + self.input_suffix
        self.add_line(line)
        words = command.split()
        if words[:1] == ['init']:
            self.handle_command_init(words[1])
        elif words[:2] == ['print', 'square']:
            self.handle_command_print_square(words[2])
        elif words[:3] == ['print', 'active', 'color']:
            self.handle_command_print_active_color()
        elif words[:2] == ['detailed', 'move']:
            # l_from and l_to are the literal words "from" and "to"
            color, piece, l_from, src_square, l_to, dst_square = words[2:]
            self.handle_command_detailed_move(color, piece, src_square, dst_square)
        else:
            raise Exception('Unsupprted command:' + command)

    def handle_command_init(self, configuration):
        if configuration == 'standard':
            self.board = get_standard_starting_board()
            self.succeed()
        elif configuration == 'empty':
            self.board = get_empty_board()
            self.succeed()
        else:
            raise Exception('Unsupprted board configuration: ' + configuration)

    def handle_command_print_square(self, square):
        if square in self.board:
            content = self.board[square]
            if content is None:
                self.succeed('empty')
            else:
                self.succeed(' '.join(content))
        else:
            raise Exception('Cannot print square:' + square)

    def handle_command_print_active_color(self):
        self.succeed(self.active_color)

    def handle_command_detailed_move(self, color, piece, src_square, dst_square):
        content = self.board.get(src_square)
        if content is None:
            raise Exception("Source square is empty")
        color, piece = content
        if color != self.active_color:
            raise Exception("Cannot move other player's piece")
        if src_square == dst_square:
            raise Exception("Piece has to move")
        if dst_square not in self.board:
            raise Exception('Destination is not a real square')
        if self.board.get(dst_square) is not None:
            raise Exception("Destination is not empty")
        self.assert_legal_move(color, piece, src_square, dst_square)
        self.board[dst_square] = self.board[src_square]
        self.board[src_square] = None
        self.switch_player()
        self.succeed()

    def switch_player(self):
        if self.active_color == 'white':
            self.active_color = 'black'
        else:
            self.active_color = 'white'

    def get_forward_direction(self, color):
        forward = +1 if color == 'black' else -1
        return forward

    def assert_legal_move(self, color, piece, src_square, dst_square):
        x0, y0 = self.square_to_xy(src_square)
        x1, y1 = self.square_to_xy(dst_square)
        dx, dy = x1 - x0, y1 - y0
        forward = self.get_forward_direction(color)
        start_y = 1 if color == 'black' else 6
        if self.board.get(dst_square) is not None:
            raise Exception("Destination is not empty")
        for int_square in self.get_intermediate_squares(src_square, dst_square):
            if self.board.get(int_square) is not None:
                raise Exception("Intermediate square is not empty: ", int_square)
        if piece == 'pawn':
            if dx != 0:
                raise Exception("Pawns cannot move sideways")
            elif sign(dy) != forward:
                raise Exception("Pawns cannot move backwards")
            elif abs(dy) > 2:
                raise Exception("Pawns cannot move more than 2 spaces")
            elif dy == 2 * forward and y0 != start_y:
                raise Exception("Pawns can only move 2 from the front rank")
            else:
                return
        else:
            raise Exception("Unsupported piece:" + piece)


    def get_intermediate_squares(self, src_square, dst_square):
        xy0 = self.square_to_xy(src_square)
        xy1 = self.square_to_xy(dst_square)
        intermediate_xys = self.get_intermediate_xys(xy0, xy1)
        return [self.xy_to_square(xy) for xy in intermediate_xys]

    def get_intermediate_xys(self, xy0, xy1):
        x0, y0 = xy0
        x1, y1 = xy1
        dx, dy = x1 - x0, y1 - y0
        if dx == 0:
            return [(x0, y) for y in range(y0, y1, sign(dy))][1:]
        elif dy == 0:
            return [(x, y0) for x in range(x0, x1, sign(dx))][1:]
        elif abs(dx) == abs(dy):
            return [(x0+i*sign(dx),y0+i*sign(dy)) for i in range(abs(dx))][1:]
        else:
            return []

    def square_to_xy(self, square):
        f, r = square
        return (FILES.index(f), RANKS.index(r))

    def xy_to_square(self, xy):
        x, y = xy
        return FILES[x] + RANKS[y]

if __name__ == '__main__':
    cli = ChessProgram()
    cli.on_line(lambda line: print(line, end=""))
    cli.handle_command('init standard')
    cli.handle_command('print active color')
    cli.handle_command('print square e2')
    cli.handle_command('print square e3')
    cli.handle_command('detailed move white pawn from e2 to e3')
    cli.handle_command('print square e2')
    cli.handle_command('print square e3')
