--!strict
-- Главный цикл игры:
--   Лобби -> Футбол (вечер) -> Хоррор (Славик проснулся) -> Итоги -> снова Лобби

local Players = game:GetService("Players")
local Lighting = game:GetService("Lighting")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage.Shared.Config)
local Remotes = require(ReplicatedStorage.Shared.Remotes)
local MapBuilder = require(script.Parent.MapBuilder)
local Football = require(script.Parent.Football)
local House = require(script.Parent.House)
local Slavik = require(script.Parent.Slavik)

local state = Remotes.state()
local messageRemote = Remotes.get("Message")
local scareRemote = Remotes.get("Scare")

local map = MapBuilder.load()
Football.init()
House.init(map)

local TEAM_NAMES: { [string]: string } = { House = "ДОМ", Fence = "СЕТКА" }

-- ===== Вспомогательное =====

local function setPhase(phase: string)
	state:SetAttribute("Phase", phase)
	print("[GameLoop] Фаза:", phase)
end

local function getPhase(): string
	local p = state:GetAttribute("Phase")
	return if typeof(p) == "string" then p else "Lobby"
end

local function say(text: string, duration: number?)
	messageRemote:FireAllClients(text, duration or 3)
end

local function getRoot(player: Player): BasePart?
	local char = player.Character
	local root = char and char:FindFirstChild("HumanoidRootPart")
	if root and root:IsA("BasePart") then
		return root
	end
	return nil
end

local atmosphere = Lighting:FindFirstChildOfClass("Atmosphere")
if not atmosphere then
	local a = Instance.new("Atmosphere")
	a.Parent = Lighting
	atmosphere = a
end
assert(atmosphere)

-- alpha 0 = начало вечера, 1 = почти ночь
local function setEvening(alpha: number)
	Lighting.ClockTime = Config.EveningStart + (Config.EveningEnd - Config.EveningStart) * alpha
	Lighting.Brightness = 2 - alpha * 1.3
	Lighting.Ambient = Color3.fromRGB(70, 60, 55):Lerp(Color3.fromRGB(30, 30, 40), alpha)
	Lighting.OutdoorAmbient = Color3.fromRGB(140, 120, 100):Lerp(Color3.fromRGB(50, 50, 65), alpha)
	atmosphere.Density = 0.3 + alpha * 0.15
	atmosphere.Color = Color3.fromRGB(200, 170, 140):Lerp(Color3.fromRGB(110, 110, 130), alpha)
	atmosphere.Haze = 1 + alpha
end

local function setNight()
	Lighting.ClockTime = Config.NightTime
	Lighting.Brightness = 0.3
	Lighting.Ambient = Color3.fromRGB(15, 15, 22)
	Lighting.OutdoorAmbient = Color3.fromRGB(30, 30, 45)
	atmosphere.Density = 0.55
	atmosphere.Color = Color3.fromRGB(70, 75, 95)
	atmosphere.Haze = 2.5
end

local function setDawn()
	Lighting.ClockTime = 6.2
	Lighting.Brightness = 1.5
	Lighting.Ambient = Color3.fromRGB(60, 55, 60)
	Lighting.OutdoorAmbient = Color3.fromRGB(120, 110, 120)
	atmosphere.Density = 0.4
	atmosphere.Color = Color3.fromRGB(220, 180, 170)
	atmosphere.Haze = 1.5
end

local function playersInsideHouse(): { Player }
	local result: { Player } = {}
	for _, player in Players:GetPlayers() do
		local root = getRoot(player)
		if root and House.isInside(root.Position) then
			table.insert(result, player)
		end
	end
	return result
end

local function assignTeams()
	local list = Players:GetPlayers()
	-- перемешиваем, чтобы команды каждый раз были разные
	for i = #list, 2, -1 do
		local j = math.random(1, i)
		list[i], list[j] = list[j], list[i]
	end
	for i, player in list do
		player:SetAttribute("Team", if i % 2 == 1 then "House" else "Fence")
	end
end

local function teamCount(team: string): number
	local n = 0
	for _, player in Players:GetPlayers() do
		if player:GetAttribute("Team") == team then
			n += 1
		end
	end
	return n
end

local function sendToTeamSpawn(player: Player)
	local char = player.Character
	if not char then
		return
	end
	local isHouse = player:GetAttribute("Team") == "House"
	local spawnPart = if isHouse then map.SpawnHouse else map.SpawnFence
	local pos = spawnPart.Position + Vector3.new(math.random(-6, 6), 0, 0)
	-- «Дом» смотрит в сторону сетки, «Сетка» — в сторону дома
	local facing = if isHouse then Vector3.new(0, 0, -1) else Vector3.new(0, 0, 1)
	char:PivotTo(CFrame.lookAt(pos, pos + facing))
end

local function sendToSpectator(player: Player)
	local char = player.Character
	if char then
		char:PivotTo(map.Spectator.CFrame + Vector3.new(math.random(-8, 8), 4, math.random(-8, 8)))
	end
end

local function catchPlayer(player: Player)
	if player:GetAttribute("Caught") == true then
		return
	end
	player:SetAttribute("Caught", true)
	scareRemote:FireClient(player, "caught")
	say(player.Name .. " пойман Славиком!", 3)
	task.delay(1.6, function()
		if player.Parent and player:GetAttribute("Caught") == true then
			sendToSpectator(player)
		end
	end)
end

-- Новые игроки и респавн
local function onPlayerAdded(player: Player)
	if getPhase() == "Football" then
		-- садим в команду, где меньше людей
		player:SetAttribute("Team", if teamCount("House") <= teamCount("Fence") then "House" else "Fence")
	end
	player.CharacterAdded:Connect(function()
		task.wait(0.1)
		if player:GetAttribute("Caught") == true and getPhase() == "Horror" then
			sendToSpectator(player)
		end
	end)
end
Players.PlayerAdded:Connect(onPlayerAdded)
for _, player in Players:GetPlayers() do
	onPlayerAdded(player)
end

-- ===== Фазы =====

local function runLobby()
	setPhase("Lobby")
	setEvening(0)
	state:SetAttribute("TimeLeft", 0)
	while true do
		while #Players:GetPlayers() < Config.MinPlayers do
			state:SetAttribute("TimeLeft", 0)
			messageRemote:FireAllClients("Ждём игроков: " .. #Players:GetPlayers() .. "/" .. Config.MinPlayers, 2)
			task.wait(2)
		end
		local ok = true
		for t = Config.LobbyCountdown, 1, -1 do
			if #Players:GetPlayers() < Config.MinPlayers then
				ok = false
				break
			end
			state:SetAttribute("TimeLeft", t)
			task.wait(1)
		end
		if ok then
			return
		end
	end
end

-- Возвращает причину пробуждения ("anger" / "time") и того, кто разбудил
local function runFootball(): (string, Player?)
	setPhase("Football")
	House.reset()
	state:SetAttribute("ScoreHouse", 0)
	state:SetAttribute("ScoreFence", 0)
	state:SetAttribute("Anger", 0)
	assignTeams()
	for _, player in Players:GetPlayers() do
		sendToTeamSpawn(player)
	end
	Slavik.spawnSleeping(map)

	local anger = 0
	local waker: Player? = nil
	local warned50, warned80 = false, false

	Football.start(map, {
		onGoal = function(team: string, scorer: Player?)
			local key = if team == "House" then "ScoreHouse" else "ScoreFence"
			local score = (state:GetAttribute(key) :: number? or 0) + 1
			state:SetAttribute(key, score)
			local who = if scorer then " (" .. scorer.Name .. ")" else ""
			say("ГОЛ! Команда " .. TEAM_NAMES[team] .. who, 2.5)
		end,
		onOverFence = function(kicker: Player?)
			anger += Config.AngerPerBallOverFence
			waker = kicker
			local who = if kicker then kicker.Name .. " перекинул мяч за сетку!" else "Мяч за сеткой!"
			say(who .. "\nДостань его... только тихо. (C — красться)", 4)
		end,
		onBallReturned = function(player: Player)
			say(player.Name .. " достал мяч. Славик ворочается...", 2.5)
		end,
	})

	say("Вечер в деревне. Играем в футбол!\nТолько не перебей через сетку — там спит Славик.", 5)

	local timeLeft = Config.FootballDuration
	local last = os.clock()
	local spot = map.SlavikSpot.Position
	local reason = "time"

	while true do
		task.wait(0.1)
		local now = os.clock()
		local dt = now - last
		last = now
		timeLeft -= dt

		if #Players:GetPlayers() == 0 then
			break
		end

		-- Шум рядом со Славиком
		local noise = 0
		for _, player in Players:GetPlayers() do
			local root = getRoot(player)
			if root and player:GetAttribute("Hidden") ~= true then
				local diff = root.Position - spot
				if Vector3.new(diff.X, 0, diff.Z).Magnitude < Config.AngerNearRadius then
					local v = root.AssemblyLinearVelocity
					local speed = Vector3.new(v.X, 0, v.Z).Magnitude
					if speed > Config.RunningSpeedThreshold then
						noise += Config.AngerPerSecondRunningNear * dt
						waker = player
					elseif speed > 1 then
						noise += Config.AngerPerSecondWalkingNear * dt
					end
				end
			end
		end
		if noise > 0 then
			anger += noise
		else
			anger = math.max(0, anger - Config.AngerDecayPerSecond * dt)
		end
		anger = math.min(anger, 100)

		state:SetAttribute("Anger", math.floor(anger))
		state:SetAttribute("TimeLeft", math.max(0, math.ceil(timeLeft)))
		setEvening(math.clamp(1 - timeLeft / Config.FootballDuration, 0, 1))

		if anger >= 50 and not warned50 then
			warned50 = true
			say("За сеткой кто-то заворочался...", 3)
		elseif anger >= 80 and not warned80 then
			warned80 = true
			say("Славик что-то бормочет во сне...", 3)
		elseif anger < 40 then
			warned50, warned80 = false, false
		end

		if anger >= 100 then
			reason = "anger"
			break
		end
		if timeLeft <= 0 then
			break
		end
	end

	Football.stop()
	return reason, waker
end

-- Возвращает "win" / "lose" / "empty"
local function runHorror(reason: string, waker: Player?): string
	setPhase("Horror")
	setNight()
	state:SetAttribute("Anger", 100)

	if reason == "anger" then
		if waker and waker.Parent then
			say(string.upper(waker.Name) .. " РАЗБУДИЛ СЛАВИКА!", 3)
		else
			say("ВЫ РАЗБУДИЛИ СЛАВИКА!", 3)
		end
	else
		say("Стемнело... Славик проснулся сам.", 3)
	end
	scareRemote:FireAllClients("wake")
	task.delay(3, function()
		if getPhase() == "Horror" then
			say("БЕГИТЕ В ДОМ И ЗАКРОЙТЕ ДВЕРЬ! (E)\nПродержитесь до рассвета.", 5)
		end
	end)

	Slavik.wake(map, {
		isDoorClosed = House.isClosed,
		onDoorHit = function()
			House.damage(Config.DoorHitDamage)
			for _, player in playersInsideHouse() do
				scareRemote:FireClient(player, "doorhit")
			end
			if House.isBroken() then
				say("ДВЕРЬ ВЫБИТА! Прячьтесь!", 3)
			end
		end,
		onCatch = catchPlayer,
		onKnock = function()
			for _, player in playersInsideHouse() do
				scareRemote:FireClient(player, "knock")
			end
			for _, player in Players:GetPlayers() do
				if player:GetAttribute("Hidden") == true then
					scareRemote:FireClient(player, "knock")
				end
			end
		end,
	})

	local timeLeft = Config.SurviveDuration
	local last = os.clock()
	local result = "win"
	local bulb = map.HouseLight
	local bulbLight = bulb and bulb:FindFirstChildOfClass("PointLight")

	while true do
		task.wait(0.25)
		local now = os.clock()
		timeLeft -= now - last
		last = now
		state:SetAttribute("TimeLeft", math.max(0, math.ceil(timeLeft)))

		-- Лампочка в доме иногда мигает
		if bulbLight and math.random() < 0.03 then
			bulbLight.Enabled = false
			task.delay(0.1 + math.random() * 0.4, function()
				bulbLight.Enabled = true
			end)
		end

		local all = Players:GetPlayers()
		if #all == 0 then
			result = "empty"
			break
		end
		local alive = 0
		for _, player in all do
			if player:GetAttribute("Caught") ~= true then
				alive += 1
			end
		end
		if alive == 0 then
			result = "lose"
			break
		end
		if timeLeft <= 0 then
			result = "win"
			break
		end
	end

	Slavik.despawn()
	if bulbLight then
		bulbLight.Enabled = true
	end
	return result
end

local function runEnd(result: string)
	setPhase("End")
	local score = "Счёт: ДОМ " .. tostring(state:GetAttribute("ScoreHouse") or 0) .. " : " .. tostring(state:GetAttribute("ScoreFence") or 0) .. " СЕТКА"
	if result == "win" then
		setDawn()
		local survivors: { string } = {}
		for _, player in Players:GetPlayers() do
			if player:GetAttribute("Caught") ~= true then
				table.insert(survivors, player.Name)
			end
		end
		say("РАССВЕТ. Славик ушёл досыпать.\nВыжили: " .. table.concat(survivors, ", ") .. "\n" .. score, Config.EndScreenDuration)
	elseif result == "lose" then
		say("Славик поймал всех...\n" .. score, Config.EndScreenDuration)
	end
	task.wait(Config.EndScreenDuration)

	House.reset()
	for _, player in Players:GetPlayers() do
		player:SetAttribute("Caught", nil)
		player:SetAttribute("Hidden", nil)
		player:LoadCharacter()
	end
end

-- ===== Поехали =====
while true do
	runLobby()
	local reason, waker = runFootball()
	if #Players:GetPlayers() > 0 then
		local result = runHorror(reason, waker)
		runEnd(result)
	else
		Slavik.despawn()
	end
end
