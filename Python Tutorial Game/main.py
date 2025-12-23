import pygame
import time
import random
pygame.font.init()

WIDTH, HEIGHT = 1000, 800
WIN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Space Dodge")

FPS = 60
BG = pygame.transform.scale_by(pygame.image.load("img/stars-galaxy.jpg"), (0.4))
player_image = pygame.transform.scale_by(pygame.image.load("img/Space_Pack/Ships/Spaceship_0.png"), (0.2))

asteroid_images = [
    pygame.transform.scale_by(pygame.image.load(f"img/Space_Pack/Asteroids/Asteroid_{i}.png"), (0.1))
    for i in range(1, 6)
]

PLAYER_WIDTH = player_image.get_width()
PLAYER_HEIGHT = player_image.get_height()
PLAYER_VEL = 5

ASTEROID_WIDTH = asteroid_images[0].get_width()
ASTEROID_HEIGHT = asteroid_images[0].get_height()
ASTEROID_VEL = 5

FONT = pygame.font.SysFont("comicsans", 30)

class Asteroid:
    def __init__(self, x, y, width, height, image):
        self.rect = pygame.Rect(x, y, width, height)
        self.image = image
    
    def __getattr__(self, name):
        return getattr(self.rect, name)

def draw(player , elapsed_time, asteroids):
    WIN.blit(BG, (0, 0))

    WIN.blit(player_image, (player.x, player.y))

    for asteroid in asteroids:
        WIN.blit(asteroid.image, (asteroid.x, asteroid.y))

    time_text = FONT.render(f"Time: {round(elapsed_time)}s", 1, "white")
    WIN.blit(time_text, (10, 10))

    pygame.display.update()

def main():
    run = True

    player = pygame.Rect((WIDTH/2-PLAYER_WIDTH/2), (HEIGHT-PLAYER_HEIGHT*2), PLAYER_WIDTH, PLAYER_HEIGHT)
    clock = pygame.time.Clock()
    start_time = time.time()
    elapsed_time = 0

    asteroid_add_increment = 2000
    asteroid_count = 0

    asteroids = []
    hit = False

    while run:
        asteroid_count += clock.tick(FPS)
        elapsed_time = time.time() - start_time

        if asteroid_count >= asteroid_add_increment:
            for _ in range(3):
                asteroid_x = random.randint(0, WIDTH - ASTEROID_WIDTH)
                asteroid_y = -ASTEROID_HEIGHT - random.randint(0, 200)
                asteroid = Asteroid(asteroid_x, asteroid_y, ASTEROID_WIDTH, ASTEROID_HEIGHT, random.choice(asteroid_images))
                asteroids.append(asteroid)

            asteroid_add_increment = max(200, asteroid_add_increment - 50)
            asteroid_count = 0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
                break
        
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] and player.x - PLAYER_VEL >= 0:
            player.x -= PLAYER_VEL
        if keys[pygame.K_RIGHT] and player.x + PLAYER_VEL + player.width <= WIDTH:
            player.x += PLAYER_VEL
        if keys[pygame.K_UP] and player.y - PLAYER_VEL >= 0:
            player.y -= PLAYER_VEL
        if keys[pygame.K_DOWN] and player.y + PLAYER_VEL + PLAYER_HEIGHT <= HEIGHT:
            player.y += PLAYER_VEL

        for asteroid in asteroids[:]:
            asteroid.rect.y += ASTEROID_VEL
            if asteroid.rect.y > HEIGHT:
                asteroids.remove(asteroid)
            elif asteroid.rect.colliderect(player):
                asteroids.remove(asteroid)
                hit = True
                break

        if hit:
            lost_text = FONT.render(f"You survived for {round(elapsed_time)} seconds!", 1, "red")
            WIN.blit(lost_text, (WIDTH/2 - lost_text.get_width()/2, HEIGHT/2 - lost_text.get_height()/2))
            pygame.display.update()
            pygame.time.delay(4000)
            break

        draw(player, elapsed_time, asteroids)

    pygame.quit()


if __name__ == "__main__":
    main()