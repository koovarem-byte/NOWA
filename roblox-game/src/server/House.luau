--!strict
-- Дом: дверь (закрыть / подпереть / сломать) и шкафы, где можно спрятаться.

local Players = game:GetService("Players")
local TweenService = game:GetService("TweenService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage.Shared.Config)
local Remotes = require(ReplicatedStorage.Shared.Remotes)
local MapBuilder = require(script.Parent.MapBuilder)

local House = {}

local map: MapBuilder.Map? = nil
local closedCF: CFrame = CFrame.new()
local openCF: CFrame = CFrame.new()
local closed = false
local broken = false
local hp = 0
local lastRepair: { [Player]: number } = {}
local togglePrompt: ProximityPrompt? = nil
local repairPrompt: ProximityPrompt? = nil

-- Шкафы: кто где сидит
local closetOwner: { [BasePart]: Player } = {}
local hideStarted: { [Player]: number } = {}
local hideCooldownUntil: { [Player]: number } = {}
local closetPrompts: { [BasePart]: ProximityPrompt } = {}

local function updateState()
	local state = Remotes.state()
	state:SetAttribute("DoorHP", hp)
	state:SetAttribute("DoorClosed", closed and not broken)
end

local function updatePrompts()
	if togglePrompt then
		togglePrompt.Enabled = not broken
		togglePrompt.ActionText = if closed then "Открыть дверь" else "Закрыть дверь"
	end
	if repairPrompt then
		repairPrompt.Enabled = closed and not broken and hp < Config.DoorMaxHP
	end
end

local function setDoor(isClosed: boolean)
	local m = map
	if not m or broken then
		return
	end
	closed = isClosed
	local tween = TweenService:Create(m.HouseDoor, TweenInfo.new(0.35), { CFrame = if closed then closedCF else openCF })
	tween:Play()
	updatePrompts()
	updateState()
end

local function breakDoor()
	local m = map
	if not m then
		return
	end
	broken = true
	closed = false
	hp = 0
	-- Выбитая дверь падает внутрь и больше не мешает
	m.HouseDoor.CanCollide = false
	TweenService:Create(m.HouseDoor, TweenInfo.new(0.4), {
		CFrame = closedCF * CFrame.new(0, -3.7, 3) * CFrame.Angles(math.rad(90), 0, 0),
		Transparency = 0.3,
	}):Play()
	updatePrompts()
	updateState()
end

local function getRoot(player: Player): BasePart?
	local char = player.Character
	local root = char and char:FindFirstChild("HumanoidRootPart")
	if root and root:IsA("BasePart") then
		return root
	end
	return nil
end

function House.unhide(player: Player)
	for closet, owner in closetOwner do
		if owner == player then
			closetOwner[closet] = nil
			local prompt = closetPrompts[closet]
			if prompt then
				prompt.ActionText = "Спрятаться"
			end
			local root = getRoot(player)
			if root and player.Character then
				root.Anchored = false
				-- Выходим перед шкафом (со стороны комнаты, -Z)
				player.Character:PivotTo(CFrame.new(closet.Position + Vector3.new(0, 0, -3)))
			end
		end
	end
	player:SetAttribute("Hidden", nil)
	hideStarted[player] = nil
	hideCooldownUntil[player] = os.clock() + Config.HideCooldown
end

local function hide(player: Player, closet: BasePart)
	local root = getRoot(player)
	if not root or not player.Character or player:GetAttribute("Caught") == true then
		return
	end
	closetOwner[closet] = player
	hideStarted[player] = os.clock()
	player:SetAttribute("Hidden", true)
	root.Anchored = true
	player.Character:PivotTo(closet.CFrame)
	local prompt = closetPrompts[closet]
	if prompt then
		prompt.ActionText = "Выйти"
	end
end

local function onClosetTriggered(closet: BasePart, player: Player)
	local owner = closetOwner[closet]
	if owner == player then
		House.unhide(player)
		return
	end
	if owner ~= nil or player:GetAttribute("Hidden") == true then
		return -- шкаф занят
	end
	if (hideCooldownUntil[player] or 0) > os.clock() then
		Remotes.get("Message"):FireClient(player, "Отдышись... в шкаф пока нельзя", 2)
		return
	end
	hide(player, closet)
end

function House.init(m: MapBuilder.Map)
	map = m
	closedCF = m.HouseDoor.CFrame
	-- Дверь открывается внутрь дома (поворот на петле)
	local hinge = m.DoorHinge.CFrame
	openCF = hinge * CFrame.Angles(0, math.rad(-90), 0) * hinge:ToObjectSpace(closedCF)

	local toggle = Instance.new("ProximityPrompt")
	toggle.ObjectText = "Дверь"
	toggle.KeyboardKeyCode = Enum.KeyCode.E
	toggle.MaxActivationDistance = 9
	toggle.RequiresLineOfSight = false
	toggle.Parent = m.HouseDoor
	toggle.Triggered:Connect(function()
		setDoor(not closed)
	end)
	togglePrompt = toggle

	local repair = Instance.new("ProximityPrompt")
	repair.ObjectText = "Дверь"
	repair.ActionText = "Подпереть дверь"
	repair.KeyboardKeyCode = Enum.KeyCode.R
	repair.HoldDuration = Config.DoorRepairHold
	repair.MaxActivationDistance = 9
	repair.RequiresLineOfSight = false
	repair.UIOffset = Vector2.new(0, 80)
	repair.Parent = m.HouseDoor
	repair.Triggered:Connect(function(player)
		local now = os.clock()
		if (lastRepair[player] or 0) + 1 > now or broken or not closed then
			return
		end
		lastRepair[player] = now
		hp = math.min(Config.DoorMaxHP, hp + Config.DoorRepairAmount)
		updatePrompts()
		updateState()
	end)
	repairPrompt = repair

	for _, closet in m.Closets do
		local prompt = Instance.new("ProximityPrompt")
		prompt.ObjectText = "Шкаф"
		prompt.ActionText = "Спрятаться"
		prompt.KeyboardKeyCode = Enum.KeyCode.E
		prompt.MaxActivationDistance = 7
		prompt.RequiresLineOfSight = false
		prompt.Parent = closet
		closetPrompts[closet] = prompt
		prompt.Triggered:Connect(function(player)
			onClosetTriggered(closet, player)
		end)
	end

	-- Долго в шкафу не просидишь
	task.spawn(function()
		while true do
			task.wait(1)
			local now = os.clock()
			for player, started in hideStarted do
				if now - started > Config.HideMaxTime then
					Remotes.get("Message"):FireClient(player, "Душно! Пришлось вылезти из шкафа", 2)
					House.unhide(player)
				end
			end
		end
	end)

	Players.PlayerRemoving:Connect(function(player)
		for closet, owner in closetOwner do
			if owner == player then
				closetOwner[closet] = nil
				local prompt = closetPrompts[closet]
				if prompt then
					prompt.ActionText = "Спрятаться"
				end
			end
		end
		hideStarted[player] = nil
		hideCooldownUntil[player] = nil
		lastRepair[player] = nil
	end)

	House.reset()
end

-- Вернуть дом в начальное состояние: дверь открыта и целая, шкафы пустые
function House.reset()
	local m = map
	if not m then
		return
	end
	for _, player in Players:GetPlayers() do
		if player:GetAttribute("Hidden") == true then
			House.unhide(player)
		end
		hideCooldownUntil[player] = nil
	end
	broken = false
	closed = false
	hp = Config.DoorMaxHP
	m.HouseDoor.CanCollide = true
	m.HouseDoor.Transparency = 0
	m.HouseDoor.CFrame = openCF
	updatePrompts()
	updateState()
end

function House.isClosed(): boolean
	return closed and not broken
end

function House.damage(amount: number)
	if not closed or broken then
		return
	end
	hp -= amount
	if hp <= 0 then
		breakDoor()
	else
		updatePrompts()
		updateState()
	end
end

function House.isInside(pos: Vector3): boolean
	local m = map
	return m ~= nil and MapBuilder.inside(m.HouseInterior, pos)
end

function House.isBroken(): boolean
	return broken
end

return House
