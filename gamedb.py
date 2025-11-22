from gamedb_ntsc_u import games_ntsc_u
from gamedb_ntsc_j import games_ntsc_j
from gamedb_pal import games_pal

games = games_ntsc_u | games_pal | games_ntsc_j
