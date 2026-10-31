--!strict
-- Мяч, удары, голы, аут и «мяч за сеткой».
-- Всё считает сервер: клиент только говорит «хочу ударить с такой силой».

local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage.Shared.Config)
local Remotes = require(ReplicatedStorage.Shared.Remotes)
local MapBuilder = require(script.Parent.MapBuilder)

export type Callbacks = {
	onGoal: (scoringTeam: string, scorer: Player?) -> (),
	onOverFence: (kicker: Player?) -> (),
	onBallReturned: (player: Player) -> (),
}

local Football = {}

local map: MapBuilder.Map? = nil
local callbacks: Callbacks? = nil
local ball: Part? = nil
local heartbeat: RBXScriptConnection? = nil
local lastKickTime: { [Player]: number } = {}
local lastKicker: Player? = nil
local overFence = false
local locked = false -- после гола мяч на пару секунд «заморожен»
local outSince: number? = nil

local function getRoot(player: Player): (BasePart?, Humanoid?)
	local char = player.Character
	if not char then
		return nil, nil
	end
	local root = char:FindFirstChild("HumanoidRootPart")
	local hum = char:FindFirstChildOfClass("Humanoid")
	if root and root:IsA("BasePart") and hum and hum.Health > 0 then
		return root, hum
	end
	return nil, nil
end

local function placeBall()
	if not ball or not map then
		return
	end
	ball.AssemblyLinearVelocity = Vector3.zero
	ball.AssemblyAngularVelocity = Vector3.zero
	ball.CFrame = CFrame.new(map.BallSpawn.Position)
	overFence = false
	outSince = nil
end

local function createBall(): Part
	local b = Instance.new("Part")
	b.Name = "Ball"
	b.Shape = Enum.PartType.Ball
	b.Size = Vector3.new(2, 2, 2)
	b.Color = Color3.fromRGB(240, 240, 240)
	b.Material = Enum.Material.SmoothPlastic
	-- лёгкий прыгучий мяч: плотность, трение, упругость
	b.CustomPhysicalProperties = PhysicalProperties.new(0.3, 0.4, 0.55, 1, 1)
	b.Parent = Workspace
	b:SetNetworkOwner(nil) -- физикой мяча управляет только сервер
	return b
end

local function onHeartbeat()
	local b = ball
	local m = map
	local cb = callbacks
	if not b or not m or not cb or locked then
		return
	end
	local pos = b.Position

	-- Голы
	if MapBuilder.inside(m.GoalHouse, pos) or MapBuilder.inside(m.GoalFence, pos) then
		-- В ворота у дома забивает команда «Сетка», в ворота у сетки — команда «Дом»
		local team = if MapBuilder.inside(m.GoalHouse, pos) then "Fence" else "House"
		locked = true
		cb.onGoal(team, lastKicker)
		task.delay(Config.GoalResetDelay, function()
			locked = false
			placeBall()
		end)
		return
	end

	-- Мяч улетел за сетку
	if not overFence and MapBuilder.inside(m.FenceZone, pos) then
		overFence = true
		cb.onOverFence(lastKicker)
	end

	-- За сеткой: кто дотронулся до мяча — тот его «перекинул» обратно
	if overFence then
		for _, player in Players:GetPlayers() do
			local root = getRoot(player)
			if root and (root.Position - pos).Magnitude < 4.5 then
				placeBall()
				cb.onBallReturned(player)
				return
			end
		end
		return
	end

	-- Аут
	local rel = pos - m.FieldCenter
	local isOut = math.abs(rel.X) > m.FieldHalfSize.X or math.abs(rel.Z) > m.FieldHalfSize.Z or pos.Y < -20
	if isOut then
		local now = os.clock()
		if not outSince then
			outSince = now
		elseif now - outSince > Config.OutResetDelay then
			placeBall()
		end
	else
		outSince = nil
	end

	-- Ведение мяча: если бежишь в мяч — он катится перед тобой
	for _, player in Players:GetPlayers() do
		local root = getRoot(player)
		if root and player:GetAttribute("Caught") ~= true then
			local diff = pos - root.Position
			local flatDist = Vector3.new(diff.X, 0, diff.Z).Magnitude
			if flatDist < Config.DribbleRange and math.abs(diff.Y) < 4 then
				local v = root.AssemblyLinearVelocity
				local flatV = Vector3.new(v.X, 0, v.Z)
				local bv = b.AssemblyLinearVelocity
				local flatB = Vector3.new(bv.X, 0, bv.Z)
				if flatV.Magnitude > 2 and flatB.Magnitude < flatV.Magnitude * Config.DribbleBoost then
					local desired = flatV * Config.DribbleBoost
					b.AssemblyLinearVelocity = Vector3.new(desired.X, math.max(bv.Y, 1), desired.Z)
				end
			end
		end
	end
end

local function onKick(player: Player, power: unknown)
	-- Проверяем всё, что прислал клиент
	if typeof(power) ~= "number" then
		return
	end
	local p = power :: number
	if p ~= p then -- NaN
		return
	end
	p = math.clamp(p, 0, 1)

	local b = ball
	if not b or locked then
		return
	end
	local now = os.clock()
	if (lastKickTime[player] or 0) + Config.KickCooldown > now then
		return
	end
	local root = getRoot(player)
	if not root or player:GetAttribute("Caught") == true then
		return
	end
	if (root.Position - b.Position).Magnitude > Config.KickRange then
		return
	end
	lastKickTime[player] = now
	lastKicker = player

	local look = root.CFrame.LookVector
	local flat = Vector3.new(look.X, 0, look.Z)
	if flat.Magnitude < 0.01 then
		return
	end
	flat = flat.Unit
	local speed = Config.KickMinSpeed + (Config.KickMaxSpeed - Config.KickMinSpeed) * p
	local lift = Config.KickMinLift + (Config.KickMaxLift - Config.KickMinLift) * p
	b.AssemblyLinearVelocity = flat * speed + Vector3.new(0, lift, 0)

	if Config.Sounds.Kick ~= "" then
		local s = Instance.new("Sound")
		s.SoundId = Config.Sounds.Kick
		s.Parent = b
		s:Play()
		task.delay(2, function()
			s:Destroy()
		end)
	end
end

function Football.init()
	Remotes.get("Kick").OnServerEvent:Connect(onKick)
	Players.PlayerRemoving:Connect(function(player)
		lastKickTime[player] = nil
		if lastKicker == player then
			lastKicker = nil
		end
	end)
end

function Football.start(m: MapBuilder.Map, cb: Callbacks)
	Football.stop()
	map = m
	callbacks = cb
	locked = false
	lastKicker = nil
	ball = createBall()
	placeBall()
	heartbeat = RunService.Heartbeat:Connect(onHeartbeat)
end

function Football.stop()
	if heartbeat then
		heartbeat:Disconnect()
		heartbeat = nil
	end
	if ball then
		ball:Destroy()
		ball = nil
	end
	callbacks = nil
end

function Football.getLastKicker(): Player?
	return lastKicker
end

function Football.isOverFence(): boolean
	return overFence
end

return Football
