--!strict
-- Славик: спит за сеткой, потом встаёт и охотится.
-- Модель собирается из блоков прямо в коде (потом заменим на нормальную).

local Players = game:GetService("Players")
local PathfindingService = game:GetService("PathfindingService")
local Workspace = game:GetService("Workspace")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage.Shared.Config)
local MapBuilder = require(script.Parent.MapBuilder)

export type Context = {
	isDoorClosed: () -> boolean,
	onDoorHit: () -> (),
	onCatch: (player: Player) -> (),
	onKnock: () -> (),
}

local Slavik = {}

local model: Model? = nil
local root: BasePart? = nil
local humanoid: Humanoid? = nil
local running = false
local snore: Sound? = nil

local HIP_HEIGHT = 2.5

local function weldPart(parent: Model, rootPart: BasePart, name: string, size: Vector3, offset: Vector3, color: Color3, material: Enum.Material?): Part
	local p = Instance.new("Part")
	p.Name = name
	p.Size = size
	p.CFrame = rootPart.CFrame * CFrame.new(offset)
	p.Color = color
	p.Material = material or Enum.Material.Fabric
	p.CanCollide = false
	p.Massless = true
	p.Anchored = false
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	local w = Instance.new("WeldConstraint")
	w.Part0 = rootPart
	w.Part1 = p
	w.Parent = p
	p.Parent = parent
	return p
end

local function build(): (Model, BasePart, Humanoid)
	local m = Instance.new("Model")
	m.Name = "Slavik"

	local r = Instance.new("Part")
	r.Name = "HumanoidRootPart"
	r.Size = Vector3.new(2, 2, 1)
	r.Transparency = 1
	r.CanCollide = true
	r.Anchored = true
	r.CFrame = CFrame.new(0, 100, 0)
	r.Parent = m
	m.PrimaryPart = r

	local coat = Color3.fromRGB(70, 62, 50)
	local skin = Color3.fromRGB(168, 160, 130)
	weldPart(m, r, "Torso", Vector3.new(2, 2, 1), Vector3.zero, coat)
	local head = weldPart(m, r, "Head", Vector3.new(1.2, 1.2, 1.2), Vector3.new(0, 1.6, 0), skin, Enum.Material.SmoothPlastic)
	weldPart(m, r, "Hat", Vector3.new(1.45, 0.55, 1.45), Vector3.new(0, 2.35, 0), Color3.fromRGB(45, 40, 35))
	weldPart(m, r, "Beard", Vector3.new(1.0, 0.5, 0.2), Vector3.new(0, 1.15, -0.6), Color3.fromRGB(90, 85, 75))
	for _, x in { -0.27, 0.27 } do
		local eye = weldPart(m, r, "Eye", Vector3.new(0.22, 0.14, 0.05), Vector3.new(x, 1.75, -0.62), Color3.fromRGB(255, 40, 30), Enum.Material.Neon)
		eye.Transparency = 1 -- глаза загораются, когда проснётся
	end
	weldPart(m, r, "LeftArm", Vector3.new(0.8, 2, 0.8), Vector3.new(-1.4, 0, 0), coat)
	weldPart(m, r, "RightArm", Vector3.new(0.8, 2, 0.8), Vector3.new(1.4, 0, 0), coat)
	-- Одна нога + костыль
	weldPart(m, r, "LeftLeg", Vector3.new(0.9, 2.5, 0.9), Vector3.new(-0.5, -2.25, 0), Color3.fromRGB(40, 40, 45))
	weldPart(m, r, "Stump", Vector3.new(0.9, 0.5, 0.9), Vector3.new(0.5, -1.25, 0), Color3.fromRGB(40, 40, 45))
	weldPart(m, r, "Crutch", Vector3.new(0.3, 3.4, 0.3), Vector3.new(1.45, -1.8, 0), Color3.fromRGB(120, 90, 55), Enum.Material.Wood)

	local glow = Instance.new("PointLight")
	glow.Name = "EyeGlow"
	glow.Color = Color3.fromRGB(255, 30, 20)
	glow.Range = 10
	glow.Brightness = 0
	glow.Parent = head

	local hum = Instance.new("Humanoid")
	hum.RigType = Enum.HumanoidRigType.R15 -- чтобы HipHeight работал для самодельной модели
	hum.HipHeight = HIP_HEIGHT
	hum.WalkSpeed = Config.SlavikSpeed
	hum.MaxHealth = 1e9
	hum.Health = 1e9
	hum.BreakJointsOnDeath = false
	hum.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
	hum.Parent = m

	return m, r, hum
end

local function playSound(parent: Instance, id: string, looped: boolean, volume: number): Sound?
	if id == "" then
		return nil
	end
	local s = Instance.new("Sound")
	s.SoundId = id
	s.Looped = looped
	s.Volume = volume
	s.RollOffMaxDistance = 80
	s.Parent = parent
	s:Play()
	if not looped then
		task.delay(6, function()
			s:Destroy()
		end)
	end
	return s
end

function Slavik.despawn()
	running = false
	if model then
		model:Destroy()
	end
	model, root, humanoid, snore = nil, nil, nil, nil
end

-- Спит на матрасе за сеткой
function Slavik.spawnSleeping(map: MapBuilder.Map)
	Slavik.despawn()
	local m, r, hum = build()
	model, root, humanoid = m, r, hum
	m:PivotTo(CFrame.new(map.SlavikSpot.Position + Vector3.new(0, 1.2, 0)) * CFrame.Angles(math.rad(-90), 0, 0))
	m.Parent = Workspace

	local gui = Instance.new("BillboardGui")
	gui.Name = "Zzz"
	gui.Size = UDim2.fromOffset(80, 40)
	gui.StudsOffsetWorldSpace = Vector3.new(0, 3, 0)
	gui.AlwaysOnTop = false
	gui.MaxDistance = 60
	local label = Instance.new("TextLabel")
	label.Size = UDim2.fromScale(1, 1)
	label.BackgroundTransparency = 1
	label.Text = "Zzz..."
	label.TextScaled = true
	label.Font = Enum.Font.Cartoon
	label.TextColor3 = Color3.fromRGB(220, 220, 255)
	label.Parent = gui
	gui.Parent = r

	snore = playSound(r, Config.Sounds.Snore, true, 0.8)
end

local function findTarget(): (Player?, BasePart?, number)
	local r = root
	if not r then
		return nil, nil, math.huge
	end
	local best: Player? = nil
	local bestRoot: BasePart? = nil
	local bestDist = math.huge
	for _, player in Players:GetPlayers() do
		if player:GetAttribute("Caught") ~= true and player:GetAttribute("Hidden") ~= true then
			local char = player.Character
			local hrp = char and char:FindFirstChild("HumanoidRootPart")
			local hum = char and char:FindFirstChildOfClass("Humanoid")
			if hrp and hrp:IsA("BasePart") and hum and hum.Health > 0 then
				local d = (hrp.Position - r.Position).Magnitude
				if d < bestDist then
					best, bestRoot, bestDist = player, hrp, d
				end
			end
		end
	end
	return best, bestRoot, bestDist
end

local function canSee(from: Vector3, target: BasePart): boolean
	local m = model
	if not m then
		return false
	end
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	local exclude: { Instance } = { m }
	local targetModel = target.Parent
	if targetModel then
		table.insert(exclude, targetModel)
	end
	params.FilterDescendantsInstances = exclude
	local result = Workspace:Raycast(from, target.Position - from, params)
	return result == nil
end

local function computePath(from: Vector3, to: Vector3): { PathWaypoint }?
	local path = PathfindingService:CreatePath({
		AgentRadius = 2,
		AgentHeight = 6,
		AgentCanJump = false,
	})
	local ok = pcall(function()
		path:ComputeAsync(from, to)
	end)
	if ok and path.Status == Enum.PathStatus.Success then
		return path:GetWaypoints()
	end
	return nil
end

local function moveAlong(hum: Humanoid, r: BasePart, waypoints: { PathWaypoint })
	for i = 2, #waypoints do
		local wp = waypoints[i].Position
		if (Vector3.new(wp.X, r.Position.Y, wp.Z) - r.Position).Magnitude > 1.5 then
			hum:MoveTo(wp)
			return
		end
	end
	hum:MoveTo(waypoints[#waypoints].Position)
end

-- Просыпается и начинает охоту
function Slavik.wake(map: MapBuilder.Map, ctx: Context)
	if not model or not root or not humanoid then
		Slavik.spawnSleeping(map)
	end
	assert(model and root and humanoid, "Славик не создан")
	local m: Model, r: BasePart, hum: Humanoid = model, root, humanoid

	local zzz = r:FindFirstChild("Zzz")
	if zzz then
		zzz:Destroy()
	end
	if snore then
		snore:Destroy()
		snore = nil
	end
	-- Глаза загораются
	for _, p in m:GetChildren() do
		if p:IsA("BasePart") and p.Name == "Eye" then
			p.Transparency = 0
		end
	end
	local head = m:FindFirstChild("Head")
	local glow = head and head:FindFirstChild("EyeGlow")
	if glow and glow:IsA("PointLight") then
		glow.Brightness = 3
	end
	playSound(r, Config.Sounds.Wake, false, 2)

	-- Встаёт (пока стоит — фора игрокам)
	local spot = map.SlavikSpot.Position
	m:PivotTo(CFrame.lookAt(spot + Vector3.new(0, 1 + HIP_HEIGHT, 0), spot + Vector3.new(0, 1 + HIP_HEIGHT, 10)))
	running = true

	task.spawn(function()
		-- Трясётся, пока поднимается
		local base = r.CFrame
		local t0 = os.clock()
		while running and os.clock() - t0 < Config.WakeUpDelay do
			r.CFrame = base * CFrame.new((math.random() - 0.5) * 0.3, 0, (math.random() - 0.5) * 0.3)
			task.wait(0.05)
		end
		if not running then
			return
		end
		r.CFrame = base
		r.Anchored = false
		r:SetNetworkOwner(nil)

		local lastDoorHit = 0
		local lastKnock = os.clock()
		local patrolTarget: Vector3? = nil

		while running and m.Parent do
			local now = os.clock()

			-- Поймал кого-то рядом?
			for _, player in Players:GetPlayers() do
				if player:GetAttribute("Caught") ~= true and player:GetAttribute("Hidden") ~= true then
					local char = player.Character
					local hrp = char and char:FindFirstChild("HumanoidRootPart")
					if hrp and hrp:IsA("BasePart") and (hrp.Position - r.Position).Magnitude < Config.CatchDistance then
						ctx.onCatch(player)
					end
				end
			end

			local target, targetRoot, dist = findTarget()
			if target and targetRoot then
				patrolTarget = nil
				hum.WalkSpeed = if dist < Config.SlavikChaseRadius then Config.SlavikChaseSpeed else Config.SlavikSpeed
				if dist < 14 and canSee(r.Position, targetRoot) then
					hum:MoveTo(targetRoot.Position) -- видит — бежит прямо
				else
					local waypoints = computePath(r.Position, targetRoot.Position)
					if waypoints then
						moveAlong(hum, r, waypoints)
					elseif ctx.isDoorClosed() then
						-- Не может пройти: идёт к двери и ломится
						local door = map.DoorOutside.Position
						local flat = Vector3.new(door.X - r.Position.X, 0, door.Z - r.Position.Z)
						if flat.Magnitude > 4 then
							local toDoor = computePath(r.Position, door)
							if toDoor then
								moveAlong(hum, r, toDoor)
							else
								hum:MoveTo(door)
							end
						elseif now - lastDoorHit > Config.DoorHitInterval then
							lastDoorHit = now
							playSound(r, Config.Sounds.DoorHit, false, 1.5)
							ctx.onDoorHit()
						end
					else
						hum:MoveTo(targetRoot.Position)
					end
				end
			else
				-- Никого не видно (все спрятались): бродит вокруг дома и стучит в окна
				hum.WalkSpeed = Config.SlavikSpeed
				if not patrolTarget or (Vector3.new(patrolTarget.X, r.Position.Y, patrolTarget.Z) - r.Position).Magnitude < 3 then
					local points = map.PatrolPoints
					if #points > 0 then
						patrolTarget = points[math.random(1, #points)].Position
					end
				end
				if patrolTarget then
					local waypoints = computePath(r.Position, patrolTarget)
					if waypoints then
						moveAlong(hum, r, waypoints)
					else
						patrolTarget = nil
					end
				end
				if now - lastKnock > Config.KnockInterval then
					lastKnock = now
					playSound(r, Config.Sounds.Knock, false, 1.5)
					ctx.onKnock()
				end
			end

			task.wait(Config.PathRecompute)
		end
	end)
end

return Slavik
