--!strict
-- Все цифры игры в одном месте. Меняй тут — остальной код трогать не нужно.

local Config = {
	-- ===== Игроки и лобби =====
	MinPlayers = 1, -- для теста одному = 1. Для настоящей игры поставь 2
	LobbyCountdown = 10, -- секунд до начала матча

	-- ===== Футбол =====
	FootballDuration = 300, -- сек. Если Славика так и не разбудили — он просыпается сам, когда стемнеет
	KickRange = 6, -- как близко надо стоять к мячу, чтобы ударить
	KickCooldown = 0.4, -- пауза между ударами одного игрока
	KickChargeTime = 1.0, -- сколько держать кнопку для удара на полную силу
	KickMinSpeed = 35, -- слабый удар (пас)
	KickMaxSpeed = 95, -- самый сильный удар
	KickMinLift = 6, -- насколько мяч подлетает при слабом ударе
	KickMaxLift = 38, -- ...и при сильном (сильный удар легко перелетит сетку!)
	DribbleRange = 3.2, -- если бежишь в мяч — он катится перед тобой
	DribbleBoost = 1.15,
	OutResetDelay = 2, -- через сколько секунд мяч из аута возвращается в центр
	GoalResetDelay = 2,

	-- ===== Сон Славика (0..100, на 100 он просыпается) =====
	AngerPerBallOverFence = 34, -- 3 мяча за сетку = Славик встал
	AngerNearRadius = 20, -- радиус, в котором Славик «слышит» шаги
	AngerPerSecondRunningNear = 12, -- бежишь рядом с ним
	AngerPerSecondWalkingNear = 2, -- крадёшься рядом с ним
	AngerDecayPerSecond = 0.5, -- потихоньку успокаивается
	RunningSpeedThreshold = 10, -- быстрее этого = «бежит»
	NormalSpeed = 16,
	SneakSpeed = 7, -- скорость, когда крадёшься (C / Ctrl / кнопка)

	-- ===== Хоррор =====
	SurviveDuration = 240, -- сколько надо продержаться до рассвета
	WakeUpDelay = 4, -- сколько секунд Славик поднимается (фора, чтобы добежать до дома)
	SlavikSpeed = 13,
	SlavikChaseSpeed = 17, -- когда игрок рядом — ускоряется
	SlavikChaseRadius = 25,
	CatchDistance = 4,
	PathRecompute = 0.35, -- как часто пересчитывать путь (сек)
	KnockInterval = 12, -- как часто стучит в окна, если никого не видит

	DoorMaxHP = 100,
	DoorHitDamage = 9,
	DoorHitInterval = 1.6,
	DoorRepairAmount = 20,
	DoorRepairHold = 1.5, -- сколько держать R, чтобы подпереть дверь
	HideMaxTime = 25, -- дольше в шкафу не высидишь — душно
	HideCooldown = 8,

	EndScreenDuration = 10,

	-- ===== Время суток (Lighting.ClockTime) =====
	EveningStart = 17.6,
	EveningEnd = 20.3,
	NightTime = 0.2,

	-- ===== Звуки =====
	-- Вставь сюда ID звуков из Creator Store (только с разрешением на использование),
	-- например "rbxassetid://1234567". Пустая строка = звука нет.
	Sounds = {
		Snore = "", -- храп Славика
		Wake = "", -- рёв, когда проснулся
		Knock = "", -- стук в окно
		DoorHit = "", -- удар в дверь
		Caught = "", -- скример
		Kick = "", -- удар по мячу
		Ambient = "", -- фон ночью (сверчки, ветер)
	},
}

return Config
