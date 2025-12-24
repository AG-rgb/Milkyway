import pygame
import random
import math
import sys

# ---------------- CONFIG ----------------
WIDTH, HEIGHT = 960, 540
FPS = 60

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (60, 60, 60)
RED = (220, 60, 60)
GREEN = (60, 220, 60)
BLUE = (60, 150, 220)
YELLOW = (250, 220, 60)
PURPLE = (170, 60, 200)

PLAYER_SPEED = 5
PLAYER_MAX_HEALTH = 100
PLAYER_LIVES = 3
PLAYER_FIRE_COOLDOWN = 250

ENEMY_BASE_SPEED = 2
ENEMY_SPAWN_INTERVAL = 1200
ENEMY_BULLET_INTERVAL = 1800

POWERUP_DURATION = 6000
POWERUP_SPAWN_CHANCE = 0.12

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Space Rogue")
clock = pygame.time.Clock()

font_small = pygame.font.SysFont("consolas", 18)
font_medium = pygame.font.SysFont("consolas", 28)
font_large = pygame.font.SysFont("consolas", 48)


# ---------------- HELPERS ----------------
def draw_text(surface, text, font, color, x, y, center=False):
    img = font.render(text, True, color)
    rect = img.get_rect()
    if center:
        rect.center = (x, y)
    else:
        rect.topleft = (x, y)
    surface.blit(img, rect)


def clamp(v, lo, hi):
    return max(lo, min(v, hi))


# ---------------- SPRITES ----------------

class Player(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.base_image = pygame.Surface((40, 40), pygame.SRCALPHA)
        pygame.draw.polygon(self.base_image, BLUE, [(20, 0), (0, 40), (40, 40)])
        self.image = self.base_image.copy()
        self.rect = self.image.get_rect(center=(WIDTH // 2, HEIGHT - 70))

        self.speed = PLAYER_SPEED
        self.health = PLAYER_MAX_HEALTH
        self.max_health = PLAYER_MAX_HEALTH
        self.lives = PLAYER_LIVES
        self.last_shot = 0

        self.powered_up = False
        self.powerup_type = None
        self.powerup_end_time = 0

        self.invincible = False
        self.invincible_end_time = 0

    def update(self, keys, now):
        dx = dy = 0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            dx -= self.speed
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            dx += self.speed
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dy -= self.speed
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dy += self.speed

        self.rect.x += dx
        self.rect.y += dy

        self.rect.left = clamp(self.rect.left, 0, WIDTH - self.rect.width)
        self.rect.top = clamp(self.rect.top, 0, HEIGHT - self.rect.height)

        if self.powered_up and now > self.powerup_end_time:
            self.powered_up = False
            self.powerup_type = None

        if self.invincible and now > self.invincible_end_time:
            self.invincible = False

        self.image = self.base_image.copy()
        if self.powered_up:
            pygame.draw.rect(self.image, YELLOW, self.image.get_rect(), 3)
        if self.invincible and (now // 100) % 2 == 0:
            self.image.fill((255, 255, 255, 80), special_flags=pygame.BLEND_RGBA_ADD)

    def shoot(self, now, bullet_group, all_sprites):
        if now - self.last_shot < (PLAYER_FIRE_COOLDOWN // (1.5 if self.powerup_type == "rapid" else 1)):
            return

        self.last_shot = now

        if self.powerup_type == "spread":
            angles = [math.radians(-10), 0, math.radians(10)]
            for angle in angles:
                b = PlayerBullet(self.rect.centerx, self.rect.top, angle)
                all_sprites.add(b)
                bullet_group.add(b)
        else:
            b = PlayerBullet(self.rect.centerx, self.rect.top, 0)
            all_sprites.add(b)
            bullet_group.add(b)

    def take_damage(self, amount, now):
        if self.invincible:
            return
        self.health -= amount
        if self.health <= 0:
            self.lives -= 1
            self.health = self.max_health
            self.invincible = True
            self.invincible_end_time = now + 2000
            self.rect.center = (WIDTH // 2, HEIGHT - 70)

    def apply_powerup(self, ptype, now):
        if ptype == "heal":
            self.health = clamp(self.health + 40, 0, self.max_health)
        elif ptype == "shield":
            self.invincible = True
            self.invincible_end_time = now + POWERUP_DURATION
        else:
            self.powered_up = True
            self.powerup_type = ptype
            self.powerup_end_time = now + POWERUP_DURATION

    def is_dead(self):
        return self.lives < 0


class PlayerBullet(pygame.sprite.Sprite):
    def __init__(self, x, y, angle):
        super().__init__()
        self.image = pygame.Surface((4, 12))
        self.image.fill(YELLOW)
        self.rect = self.image.get_rect(centerx=x, bottom=y)
        self.speed = -10
        self.vx = math.sin(angle) * abs(self.speed)
        self.vy = -abs(math.cos(angle) * abs(self.speed))

    def update(self):
        self.rect.x += self.vx
        self.rect.y += self.vy
        if self.rect.bottom < 0:
            self.kill()


class Enemy(pygame.sprite.Sprite):
    def __init__(self, x, y, etype, level):
        super().__init__()
        self.etype = etype
        size = 30 if etype == "chaser" else 35
        self.image = pygame.Surface((size, size))
        self.image.fill(RED if etype == "chaser" else PURPLE)
        self.rect = self.image.get_rect(center=(x, y))

        self.base_speed = ENEMY_BASE_SPEED + level * 0.1
        self.health = 30 + level * 5 if etype == "chaser" else 40 + level * 7
        self.score_value = 20 if etype == "chaser" else 35
        self.shoot_timer = 0
        self.zigzag_dir = 1

    def update(self, player, now, enemy_bullets, all_sprites):
        if self.etype == "chaser":
            dx = player.rect.centerx - self.rect.centerx
            dy = player.rect.centery - self.rect.centery
            dist = math.hypot(dx, dy) + 0.001
            self.rect.x += (dx / dist) * self.base_speed
            self.rect.y += (dy / dist) * self.base_speed * 0.85

        elif self.etype == "shooter":
            self.rect.y += self.base_speed * 0.6
            self.rect.x += self.base_speed * (1 if (now // 700) % 2 == 0 else -1)

            if now - self.shoot_timer > ENEMY_BULLET_INTERVAL:
                self.shoot_timer = now
                b = EnemyBullet(self.rect.centerx, self.rect.bottom)
                all_sprites.add(b)
                enemy_bullets.add(b)

        elif self.etype == "zigzag":
            self.rect.y += self.base_speed
            self.rect.x += self.zigzag_dir * self.base_speed * 1.5
            if self.rect.left <= 0 or self.rect.right >= WIDTH:
                self.zigzag_dir *= -1

        if self.rect.top > HEIGHT:
            self.kill()

    def damage(self, amount):
        self.health -= amount
        return self.health <= 0


class EnemyBullet(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((4, 10))
        self.image.fill(WHITE)
        self.rect = self.image.get_rect(centerx=x, top=y)
        self.speed = 6

    def update(self):
        self.rect.y += self.speed
        if self.rect.top > HEIGHT:
            self.kill()


class Powerup(pygame.sprite.Sprite):
    def __init__(self, x, y, ptype):
        super().__init__()
        self.ptype = ptype
        self.image = pygame.Surface((20, 20))
        self.image.fill(GREEN if ptype == "heal" else BLUE if ptype == "shield" else YELLOW)
        self.rect = self.image.get_rect(center=(x, y))
        self.speed = 2

    def update(self):
        self.rect.y += self.speed
        if self.rect.top > HEIGHT:
            self.kill()


class Star(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        size = random.randint(1, 3)
        self.image = pygame.Surface((size, size))
        self.image.fill(WHITE)
        self.rect = self.image.get_rect(
            x=random.randint(0, WIDTH),
            y=random.randint(0, HEIGHT)
        )
        self.speed = random.uniform(0.5, 2.0)

    def update(self):
        self.rect.y += self.speed
        if self.rect.top > HEIGHT:
            self.rect.bottom = 0
            self.rect.x = random.randint(0, WIDTH)


# ---------------- GAME MANAGER ----------------

class Game:
    def __init__(self):
        self.running = True
        self.paused = False
        self.game_over = False

        self.all_sprites = pygame.sprite.Group()
        self.player_bullets = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        self.enemy_bullets = pygame.sprite.Group()
        self.powerups = pygame.sprite.Group()

        for _ in range(80):
            s = Star()
            self.all_sprites.add(s)

        self.player = Player()
        self.all_sprites.add(self.player)

        self.score = 0
        self.level = 1
        self.last_enemy_spawn = 0
        self.next_wave_threshold = 200

    def reset(self):
        self.__init__()

    def spawn_enemy(self, now):
        etype = random.choices(["chaser", "shooter", "zigzag"], weights=[0.5, 0.3, 0.2])[0]
        x = random.randint(40, WIDTH - 40)
        y = random.randint(-80, -40)
        e = Enemy(x, y, etype, self.level)
        self.all_sprites.add(e)
        self.enemies.add(e)
        self.last_enemy_spawn = now

    def maybe_spawn_powerup(self, x, y):
        if random.random() < POWERUP_SPAWN_CHANCE:
            ptype = random.choice(["heal", "shield", "rapid", "spread"])
            p = Powerup(x, y, ptype)
            self.all_sprites.add(p)
            self.powerups.add(p)

    def update(self, dt):
        if self.paused or self.game_over:
            return

        now = pygame.time.get_ticks()
        keys = pygame.key.get_pressed()

        if now - self.last_enemy_spawn > max(450, ENEMY_SPAWN_INTERVAL - self.level * 40):
            self.spawn_enemy(now)

        if self.score >= self.next_wave_threshold:
            self.level += 1
            self.next_wave_threshold += 250 + self.level * 150

        # Update non-player sprites
        for sprite in self.all_sprites:
            if sprite is not self.player:
                if isinstance(sprite, Enemy):
                    sprite.update(self.player, now, self.enemy_bullets, self.all_sprites)
                else:
                    sprite.update()

        # Update player separately
        self.player.update(keys, now)

        if keys[pygame.K_SPACE]:
            self.player.shoot(now, self.player_bullets, self.all_sprites)

        self.handle_collisions(now)

        if self.player.is_dead():
            self.game_over = True

    def handle_collisions(self, now):
        hits = pygame.sprite.groupcollide(self.enemies, self.player_bullets, False, True)
        for enemy, bullets in hits.items():
            if enemy.damage(20 * len(bullets)):
                self.score += enemy.score_value
                x, y = enemy.rect.center
                enemy.kill()
                self.maybe_spawn_powerup(x, y)

        if pygame.sprite.spritecollide(self.player, self.enemy_bullets, True):
            self.player.take_damage(15, now)

        if pygame.sprite.spritecollide(self.player, self.enemies, True):
            self.player.take_damage(35, now)

        for p in pygame.sprite.spritecollide(self.player, self.powerups, True):
            self.player.apply_powerup(p.ptype, now)

    def draw_hud(self, surface):
        bar_w = 200
        bar_h = 18
        x, y = 20, 20

        pygame.draw.rect(surface, GRAY, (x, y, bar_w, bar_h))
        pygame.draw.rect(surface, GREEN, (x, y, bar_w * (self.player.health / self.player.max_health), bar_h))
        pygame.draw.rect(surface, WHITE, (x, y, bar_w, bar_h), 2)

        draw_text(surface, f"Lives: {max(0, self.player.lives)}", font_small, WHITE, x, y + 28)
        draw_text(surface, f"Score: {self.score}", font_small, WHITE, WIDTH - 160, 20)
        draw_text(surface, f"Level: {self.level}", font_small, WHITE, WIDTH - 160, 40)

        if self.player.powered_up:
            draw_text(surface, f"Power: {self.player.powerup_type}", font_small, YELLOW, x, y + 48)

    def draw_pause(self, surface):
        draw_text(surface, "PAUSED", font_large, WHITE, WIDTH // 2, HEIGHT // 2 - 40, center=True)
        draw_text(surface, "Press P to resume", font_medium, GRAY, WIDTH // 2, HEIGHT // 2 + 10, center=True)

    def draw_game_over(self, surface):
        draw_text(surface, "GAME OVER", font_large, RED, WIDTH // 2, HEIGHT // 2 - 60, center=True)
        draw_text(surface, f"Final Score: {self.score}", font_medium, WHITE, WIDTH // 2, HEIGHT // 2, center=True)
        draw_text(surface, "Press R to restart or ESC to quit", font_small, GRAY, WIDTH // 2, HEIGHT // 2 + 50, center=True)

    def draw(self, surface):
        surface.fill(BLACK)
        self.all_sprites.draw(surface)
        self.draw_hud(surface)

        if self.paused and not self.game_over:
            self.draw_pause(surface)

        if self.game_over:
            self.draw_game_over(surface)


# ---------------- MAIN LOOP ----------------

def main():
    game = Game()

    while game.running:
        dt = clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    game.running = False
                if event.key == pygame.K_p and not game.game_over:
                    game.paused = not game.paused
                if event.key == pygame.K_r and game.game_over:
                    game.reset()

        game.update(dt)
        game.draw(screen)
        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
