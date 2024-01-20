from shapely.geometry import Point, Polygon
from collections import Counter
import pygame_menu
import logging
import pygame
import random
import json
import sys
import re
import os


logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S"
)

logger = logging.getLogger(__name__)

# Constants
current_path = os.path.dirname(os.path.abspath(__file__))
ASSETS_PATH = os.path.join(current_path, 'assets')
MEMES_PATH = os.path.join(ASSETS_PATH, 'memes')
MEMES = [os.path.join(ASSETS_PATH, 'memes', x) for x in os.listdir(MEMES_PATH)]
DRIVERS = json.load(open(os.path.join(ASSETS_PATH, 'drivers.json'), 'r'))
TEAMS = {x['driver']: x['team'] for x in DRIVERS['drivers']}
WIDTH, HEIGHT = 1200, 800
GRID_SIZE = 60
MEME_WIDTH = 150


class Meme(pygame.sprite.Sprite):
    """
    The Meme class, for handling the meme in the meme game about meme trains.

    Parameters
    ----------
    x : int
        The x position of the meme.
    y : int
        The y position of the meme.
    width : int
        The width of the meme.
    exclude_image : list[str] | None
        A list of images to exclude from the list of memes. 
        This is useful when you want to exclude an image that has already been used for the previous meme.

    Attributes
    ----------
    width : int
        The width of the meme.
    x : int
        The x position of the meme.
    y : int
        The y position of the meme.
    meme_image : str
        The path to the meme image.
    driver_name : str
        The name of the driver.
    team : str
        The team of the driver.
    image : pygame.Surface
        The pygame image object.
    position : tuple[int, int]
        The position of the meme.
    meme_box : shapely.geometry.Polygon
        The outline of the meme.
    """
    def __init__(
            self, 
            x: int,
            y: int,
            width: int,
            exclude_image: list[str] | None = None,
        ) -> None:
        super().__init__()
        self.width = width
        self.x, self.y = x, y
        if exclude_image is not None:
            self.meme_image = random.choice([x for x in MEMES if x not in exclude_image])
        else:
            self.meme_image = random.choice(MEMES)

        self.driver_name = re.sub(
            r'[0-9]', 
            '', 
            os.path.basename(self.meme_image.replace('.png', ''))
        )
        self.team = TEAMS.get(self.driver_name, None)

        self.image = pygame.image.load(self.meme_image)
        
        # Scale the image
        orig_width, orig_height = self.image.get_size()
        aspect_ratio = orig_width / orig_height
        self.width = width
        self.height = int(width / aspect_ratio)
        self.image = pygame.transform.scale(self.image, (self.width, self.height))
        logger.debug(f"Loaded meme: {self.meme_image}")
        logger.debug(f"Driver: {self.driver_name}") 
        logger.debug(f"Team: {self.team}")
        logger.debug(f"Width: {self.width}; Height: {self.height}")
        logger.debug(f"Position: {self.position}")
        logger.debug(f"Edges: {self.meme_box.exterior.coords.xy}")
        
    @property
    def position(self) -> tuple[int, int]:
        return (self.x * GRID_SIZE, self.y * GRID_SIZE)
    
    @property
    def meme_box(self) -> Polygon:
        x, y, width, height = self.x  * GRID_SIZE, self.y * GRID_SIZE, self.width, self.height
        return Polygon(
            [
                (x, y), 
                (x + width, y), 
                (x + width, y + height), 
                (x, y + height), 
                (x, y)
            ]
        )
            


class MemeTrain:
    """
    The MemeTrain class, for handling the meme train game.
    """
    def __init__(self, fullscreen: bool = True):
        pygame.init()
        pygame.mixer.init()
        self.screen = (
            pygame.display.set_mode((0, 0), pygame.FULLSCREEN) 
            if fullscreen else pygame.display.set_mode((1200, 800))
        )
        info = pygame.display.Info()
        self.screen_width = info.current_w
        self.screen_height = info.current_h
        # Setup the grid
        self.grid_width = self.screen_width // GRID_SIZE
        self.grid_height = self.screen_height // GRID_SIZE
        logger.debug(f"Grid width: {self.grid_width}; Grid height: {self.grid_height}")
        pygame.display.set_caption("Choo choo...all aboard the meme train.")
        self.clock = pygame.time.Clock()
        self.running = False

        # Initialize snake
        self.snake = [(self.grid_width // 2, self.grid_height // 2)]
        self.snake_images = [
            pygame.transform.scale(
                pygame.image.load(os.path.join(ASSETS_PATH, 'cars', 'safetycar.png')),
                (20, 50)
            )
        ]
        self.snake_direction = (0, 1)
        self.snake_speed = 4
        

        # Initialize a meme
        x, y = self.random_grid_position()
        while x == self.snake[0][0] and y == self.snake[0][1]:
            x, y = self.random_grid_position()
        self.meme = Meme(
            x=x,
            y=y,
            width=MEME_WIDTH,
            exclude_image=[
                os.path.join(ASSETS_PATH, 'memes', x) for x in [
                    'verstappen1.png',
                    'verstappen2.png',
                    'verstappen3.png',
                    'verstappen4.png',
                ]
            ]
        )
        logger.debug(f"Snake: {self.snake}")
        logger.debug(f"Meme: {self.meme.driver_name}")
        logger.debug(f"Snake direction: {self.snake_direction}")

        # Initialize sounds
        self.super_max = False
        self.super_max_sound = pygame.mixer.Sound(os.path.join(ASSETS_PATH, 'sound', 'super-max.mp3'))
        self.menu_sound = pygame.mixer.Sound(os.path.join(ASSETS_PATH, 'sound', 'menu.mp3'))
        self.meme_sound = None
        self.teams_collected = []
        
        # Setup the menu
        menu_theme = pygame_menu.themes.Theme(
            background_color=(0, 0, 0, 0),  # Transparent background
            title_background_color=(4, 47, 126),
            title_font_color=(255, 255, 255),
            title_font=pygame_menu.font.FONT_8BIT,
            widget_font=pygame_menu.font.FONT_8BIT,
            widget_font_color=(255, 170, 0),
            selection_color=(255, 255, 0)
        )
        
        self.menu = pygame_menu.Menu(
            title="F1 MemeTrain",
            height=400, 
            width=700, 
            theme=menu_theme
        )
        self.setup_menu()
        self.menu.mainloop(self.screen)

    def setup_menu(self) -> None:
        """
        Add the menu items to the menu.
        """
        self.menu.add.selector('Speed :', [('Haas', 4), ('McLaren', 7), ('Red Bull', 9)], onchange=self.set_difficulty)
        self.menu.add.button('Play', self.start_game)
        self.menu.add.button('Quit', pygame_menu.events.EXIT)
        self.menu_sound.play()
    
    def set_difficulty(self, value, difficulty):
        """
        Set the difficulty of the game.
        """
        self.snake_speed = difficulty
        logger.debug(f"Difficulty set to {difficulty}")

    def start_game(self) -> None:
        """
        Start the game - reset all the variables.
        """
        self.running = True
        self.menu_sound.stop()
        self.run_meme_sound()

        self.snake = [(self.grid_width // 2, self.grid_height // 2)]
        self.snake_images = [
            pygame.transform.scale(
                pygame.image.load(os.path.join(ASSETS_PATH, 'cars', 'safetycar.png')),
                (20, 50)
            )
        ]
        self.teams_collected = []
        self.snake_direction = (0, 1)

        # Disable menu
        self.menu.disable()
        self.menu.full_reset()
        logger.debug("Game started")
        self.main_loop()

    def exit_to_menu(self) -> None:
        """
        Exit the game and return to the menu.
        """
        logger.debug("Exited to menu")
        self.meme_sound.stop()
        self.super_max_sound.stop()
        self.running = False
        self.menu.enable()
        self.menu_sound.play()

    def handle_events(self):
        """
        Handle input events.
        """
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                pygame.quit()
                sys.exit(0)
            elif event.type == pygame.KEYDOWN:
                logger.debug(f"Key pressed: {event.key}")
                if event.key == pygame.K_ESCAPE:
                    self.exit_to_menu()
                elif event.key == pygame.K_UP and self.snake_direction != (0, 1):
                    self.snake_direction = (0, -1)
                elif event.key == pygame.K_DOWN and self.snake_direction != (0, -1):
                    self.snake_direction = (0, 1)
                elif event.key == pygame.K_LEFT and self.snake_direction != (1, 0):
                    self.snake_direction = (-1, 0)
                elif event.key == pygame.K_RIGHT and self.snake_direction != (-1, 0):
                    self.snake_direction = (1, 0)

    def get_snake_head_rotation(self):
        """
        Get the rotation of the snake head.
        """
        # Maps direction to rotation angle (in degrees)
        direction_to_angle = {
            (0, -1): 0,   # Up
            (0, 1): 180,  # Down
            (-1, 0): 90,  # Left
            (1, 0): 270   # Right
        }
        return direction_to_angle[self.snake_direction]
    
    def random_grid_position(self):
        """
        Get a random grid position - excluding the edges.
        """
        return (random.randint(2, self.grid_width - 3), random.randint(2, self.grid_height - 3))
    
    def meme_collision(self):
        """
        Check for collisions with the meme.
        """
        return self.meme.meme_box.intersects(
            Point((self.snake[0][0] * GRID_SIZE, self.snake[0][1] * GRID_SIZE))
        )
    
    def snake_collision(self):
        """
        Handle collisions with the snake.
        """
        # Check for collisions with itself (including the head)
        logger.debug(f"Snake: {self.snake}")
        if len(self.snake) != len(set(self.snake)):
            logger.debug("Snake collided with itself")
            self.meme_sound.stop()
            self.super_max_sound.stop()
            
            exit_sound = pygame.mixer.Sound(os.path.join(ASSETS_PATH, 'sound', 'exit.mp3'))
            exit_sound.play()

            crash_image = pygame.image.load(os.path.join(ASSETS_PATH, 'memes', 'toto2.png'))
            orig_width, orig_height = crash_image.get_size()
            aspect_ratio = orig_width / orig_height
            crash_image = pygame.transform.scale(crash_image, (500, int(500 / aspect_ratio)))
            crash_image_rect = crash_image.get_rect(center=(self.screen_width/2, self.screen_height/2))

            font = pygame.font.Font(pygame_menu.font.FONT_BEBAS, 36)
            text1 = font.render("No Mikey! No!", 1, (255, 0, 0))
            text1_rect = text1.get_rect(center=(self.screen_width/2, self.screen_height/2 + crash_image_rect.height / 2 + 20))
            text1_surface = pygame.Surface(text1.get_size())
            text1_surface.fill((0, 0, 0))

            text2 = font.render("Press space key to exit", 1, (255, 0, 0))
            text2_rect = text2.get_rect(center=(self.screen_width/2, text1_rect.bottom + 20))
            text2_surface = pygame.Surface(text2.get_size())
            text2_surface.fill((0, 0, 0))
            
            # Blit the image and texts
            self.screen.blit(crash_image, crash_image_rect)
            self.screen.blit(text1_surface, text1_rect)
            self.screen.blit(text2_surface, text2_rect)
            self.screen.blit(text1, text1_rect)
            self.screen.blit(text2, text2_rect)


            # Update the display
            pygame.display.flip()
            # Wait for a key press
            return self._exit_after_win_lose()
                    
    def win(self):
        """
        Handle winning the game.
        """
        self.meme_sound.stop()
        self.super_max_sound.stop()

        win_sound = pygame.mixer.Sound(os.path.join(ASSETS_PATH, 'sound', 'win.mp3'))
        win_sound.play()

        win_image = pygame.image.load(os.path.join(ASSETS_PATH, 'win.jpg'))
        orig_width, orig_height = win_image.get_size()
        aspect_ratio = orig_width / orig_height
        win_image = pygame.transform.scale(win_image, (500, int(500 / aspect_ratio)))
        win_image_rect = win_image.get_rect(center=(self.screen_width/2, self.screen_height/2))
        
        font = pygame.font.Font(pygame_menu.font.FONT_BEBAS, 36)
        text1 = font.render("You collected all the things!  Nice!", 1, (255, 0, 0))
        text1_rect = text1.get_rect(center=(self.screen_width/2, self.screen_height/2 + win_image_rect.height / 2 + 20))
        text1_surface = pygame.Surface(text1.get_size())
        text1_surface.fill((0, 0, 0))

        text2 = font.render("Press space key to exit", 1, (255, 0, 0))
        text2_rect = text2.get_rect(center=(self.screen_width/2, text1_rect.bottom + 20))
        text2_surface = pygame.Surface(text2.get_size())
        text2_surface.fill((0, 0, 0))

        # Blit the image and texts
        self.screen.blit(win_image, win_image_rect)
        self.screen.blit(text1_surface, text1_rect)
        self.screen.blit(text2_surface, text2_rect)
        self.screen.blit(text1, text1_rect)
        self.screen.blit(text2, text2_rect)


        # Update the display
        pygame.display.flip()
        # Wait for a key press
        return self._exit_after_win_lose()
                
    def _exit_after_win_lose(self):
        """
        Wait for a key press to exit the game, then return to the menu.
        """
        while True:
            for event in pygame.event.get():
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        self.exit_to_menu()
                        return
    
    def move_snake(self):
        """
        Move the elements of the snake.
        """
        x, y = self.snake[0]
        new_head = (x + self.snake_direction[0], y + self.snake_direction[1])

        # Wrap the snake around the screen
        new_head = (new_head[0] % self.grid_width, new_head[1] % self.grid_height)

        self.snake.insert(0, new_head)

        # Check for collisions with meme
        if self.meme_collision():
            # Add to the snake
            self.snake_images.append(
                pygame.transform.scale(
                    pygame.image.load(os.path.join(ASSETS_PATH, 'cars', f'{self.meme.team}.png')),
                    (20, 50)
                )
            )
            self.teams_collected.append(self.meme.team)
            # Check if two memes for every team have been collected
            if set(self.teams_collected) == set(TEAMS.values()):
                if all([x >= 2 for x in Counter(self.teams_collected).values()]):
                    return self.win()

            # Add a new meme
            x, y = self.random_grid_position()
            while (
                x == self.snake[0][0] and y == self.snake[0][1]
            ) & (
                self.meme.meme_box.intersects(Point((x * GRID_SIZE, y * GRID_SIZE)))
            ):
                x, y = self.random_grid_position()
            self.meme = Meme(
                x=x,
                y=y,
                width=MEME_WIDTH,
                exclude_image=self.meme.meme_image
            )
            self.super_max = self.meme.driver_name == 'verstappen'
            if self.super_max:
                self.play_super_max()
            else:
                self.stop_super_max()
                self.run_meme_sound()
        else:
            self.snake.pop()
        self.snake_collision()

    def run_meme_sound(self):
        """
        Run the meme sound.
        """
        if self.meme_sound is not None:
            self.meme_sound.stop()
        if f'{self.meme.driver_name}.mp3' in os.listdir(os.path.join(ASSETS_PATH, 'sound')):
            self.meme_sound = pygame.mixer.Sound(os.path.join(ASSETS_PATH, 'sound', f'{self.meme.driver_name}.mp3'))
        else:
            self.meme_sound = pygame.mixer.Sound(os.path.join(ASSETS_PATH, 'sound', 'f1-radio.mp3'))
        self.meme_sound.play()

    def get_segment_direction(self, current_segment, next_segment):
        """
        Get the direction of a segment using the current and next segment.
        """
        # Determine the direction based on the position of the next segment
        if next_segment[0] > current_segment[0]:
            return 'right'
        elif next_segment[0] < current_segment[0]:
            return 'left'
        elif next_segment[1] > current_segment[1]:
            return 'down'
        elif next_segment[1] < current_segment[1]:
            return 'up'
        
    def play_super_max(self):
        """
        Play the super max sound.
        """
        if self.meme_sound is not None:
            self.meme_sound.stop()
        self.super_max_sound.play(-1)

    def stop_super_max(self):
        """
        Stop the super max sound.
        """
        self.super_max_sound.stop()
        
    def draw_objects(self):
        """
        Draw all the objects on the screen.
        """
        if self.super_max:
            screen_size = self.screen.get_size()
            background_image = pygame.image.load(os.path.join(ASSETS_PATH, 'Netherlands.png'))
            background_image = pygame.transform.scale(background_image, screen_size)
            self.screen.blit(background_image, (0, 0))
        else:
            self.screen.fill((0,0,0))

        # Draw the meme
        rect = self.meme.image.get_rect()
        rect.topleft = self.meme.position
        self.screen.blit(self.meme.image, rect)

        # Draw the snake
        for i, segment in enumerate(self.snake):
            direction = None
            image = self.snake_images[i]
            if i == 0:
                # Use the current direction for the head
                angle = self.get_snake_head_rotation()
            else:
                # Determine the direction of the segment
                direction = self.get_segment_direction(segment, self.snake[i - 1])
                angle = {'up': 0, 'down': 180, 'left': 90, 'right': 270}.get(direction, 0)
            
            # Rotate the image based on the direction
            rotated_image = pygame.transform.rotate(image, angle)

            # Get the new size of the rotated image
            image_rect = rotated_image.get_rect()

            # Calculate the position of the segment
            segment_x = segment[0] * GRID_SIZE + (GRID_SIZE - image_rect.width) // 2
            segment_y = segment[1] * GRID_SIZE + (GRID_SIZE - image_rect.height) // 2
            self.screen.blit(rotated_image, (segment_x, segment_y))
        
        pygame.display.update()

    def main_loop(self):
        """
        The main loop of the game.
        """
        while self.running:
            self.handle_events()
            self.move_snake()
            self.draw_objects()
            self.clock.tick(self.snake_speed)

        if self.menu.is_enabled():
            self.menu.mainloop(self.screen)



if __name__ == "__main__":
    MemeTrain()