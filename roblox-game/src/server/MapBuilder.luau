--!strict
-- Карта-заглушка («серая коробка»).
-- Если в Workspace уже есть папка "Map" (твоя настоящая локация) — ничего не строим,
-- просто находим в ней нужные объекты по именам (список имён — в README.md).

local Workspace = game:GetService("Workspace")

export type Map = {
	Folder: Instance,
	BallSpawn: BasePart,
	GoalHouse: BasePart, -- ворота у дома
	GoalFence: BasePart, -- ворота у сетки
	FenceZone: BasePart, -- зона за сеткой (там спит Славик)
	SlavikSpot: BasePart,
	SpawnHouse: BasePart, -- откуда стартует команда «Дом»
	SpawnFence: BasePart, -- откуда стартует команда «Сетка»
	HouseDoor: BasePart,
	DoorHinge: BasePart,
	DoorOutside: BasePart, -- точка перед дверью снаружи
	HouseInterior: BasePart,
	HouseLight: BasePart?,
	Closets: { BasePart },
	PatrolPoints: { BasePart },
	Spectator: BasePart, -- куда попадают пойманные
	FieldCenter: Vector3,
	FieldHalfSize: Vector3, -- за этими границами мяч считается в ауте
}

local MapBuilder = {}

local GRASS = Color3.fromRGB(70, 92, 52)
local DIRT = Color3.fromRGB(110, 88, 60)
local WOOD = Color3.fromRGB(105, 74, 46)
local DARK_WOOD = Color3.fromRGB(70, 50, 32)
local METAL = Color3.fromRGB(150, 150, 150)

local function part(
	parent: Instance,
	name: string,
	size: Vector3,
	cf: CFrame,
	color: Color3,
	material: Enum.Material?
): Part
	local p = Instance.new("Part")
	p.Name = name
	p.Size = size
	p.CFrame = cf
	p.Color = color
	p.Material = material or Enum.Material.SmoothPlastic
	p.Anchored = true
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	p.Parent = parent
	return p
end

-- Невидимая служебная деталь (триггер, точка)
local function marker(parent: Instance, name: string, size: Vector3, pos: Vector3): Part
	local p = part(parent, name, size, CFrame.new(pos), Color3.new(1, 0, 0))
	p.Transparency = 1
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	return p
end

local function lamp(parent: Instance, pos: Vector3, range: number)
	part(parent, "LampPole", Vector3.new(0.6, 14, 0.6), CFrame.new(pos + Vector3.new(0, 7, 0)), DARK_WOOD, Enum.Material.Wood)
	local head = part(
		parent,
		"LampHead",
		Vector3.new(1.4, 0.8, 1.4),
		CFrame.new(pos + Vector3.new(0, 14.2, 0)),
		Color3.fromRGB(255, 214, 150),
		Enum.Material.Neon
	)
	local light = Instance.new("PointLight")
	light.Range = range
	light.Brightness = 2
	light.Color = Color3.fromRGB(255, 200, 130)
	light.Shadows = true
	light.Parent = head
end

local function build(): Instance
	local map = Instance.new("Folder")
	map.Name = "Map"

	-- Земля и поле
	part(map, "Ground", Vector3.new(400, 1, 400), CFrame.new(0, -0.5, 0), GRASS, Enum.Material.Grass)
	part(map, "Field", Vector3.new(64, 0.2, 110), CFrame.new(0, 0.1, 0), DIRT, Enum.Material.Ground)

	-- Боковые бортики (низкие доски)
	for _, x in { -34, 34 } do
		part(map, "SideBoard", Vector3.new(0.5, 2.5, 118), CFrame.new(x, 1.25, 1), WOOD, Enum.Material.WoodPlanks)
	end

	-- Импровизированные ворота: ящики вместо штанг
	local function goal(name: string, z: number, triggerZ: number)
		for _, x in { -5.5, 5.5 } do
			part(map, name .. "Post", Vector3.new(2, 5, 2), CFrame.new(x, 2.5, z), WOOD, Enum.Material.WoodPlanks)
		end
		marker(map, name, Vector3.new(9, 5, 2), Vector3.new(0, 2.5, triggerZ))
	end
	goal("GoalHouse", 50, 51.5)
	goal("GoalFence", -50, -51.5)

	-- Сетка-рабица за воротами, с калиткой (дыра x 28..34)
	local fenceH = 12
	local function fenceSegment(size: Vector3, pos: Vector3)
		local f = part(map, "Fence", size, CFrame.new(pos), METAL, Enum.Material.DiamondPlate)
		f.Transparency = 0.45
	end
	fenceSegment(Vector3.new(68, fenceH, 0.3), Vector3.new(-6, fenceH / 2, -58)) -- x -40..28
	fenceSegment(Vector3.new(6, fenceH, 0.3), Vector3.new(37, fenceH / 2, -58)) -- x 34..40
	fenceSegment(Vector3.new(0.3, fenceH, 37), Vector3.new(-40, fenceH / 2, -76.5))
	fenceSegment(Vector3.new(0.3, fenceH, 37), Vector3.new(40, fenceH / 2, -76.5))
	fenceSegment(Vector3.new(80, fenceH, 0.3), Vector3.new(0, fenceH / 2, -95))
	for x = -40, 40, 10 do
		part(map, "FencePole", Vector3.new(0.5, fenceH + 0.5, 0.5), CFrame.new(x, (fenceH + 0.5) / 2, -58), DARK_WOOD)
	end
	marker(map, "FenceZone", Vector3.new(80, 40, 36.5), Vector3.new(0, 20, -76.75))

	-- Лежбище Славика: матрас и коробки
	part(map, "Mattress", Vector3.new(4, 0.6, 7), CFrame.new(0, 0.3, -75), Color3.fromRGB(120, 110, 80), Enum.Material.Fabric)
	part(map, "Box", Vector3.new(3, 2.5, 3), CFrame.new(5, 1.25, -78) * CFrame.Angles(0, 0.4, 0), Color3.fromRGB(150, 120, 80), Enum.Material.Cardboard)
	part(map, "Box", Vector3.new(2, 2, 2), CFrame.new(-4.5, 1, -72) * CFrame.Angles(0, -0.3, 0), Color3.fromRGB(150, 120, 80), Enum.Material.Cardboard)
	marker(map, "SlavikSpot", Vector3.new(1, 1, 1), Vector3.new(0, 0, -75))

	-- ===== Дом (x -15..15, z 62..86) =====
	local house = Instance.new("Folder")
	house.Name = "House"
	house.Parent = map
	local wallH = 12
	local function wall(size: Vector3, pos: Vector3)
		part(house, "Wall", size, CFrame.new(pos), Color3.fromRGB(140, 110, 80), Enum.Material.WoodPlanks)
	end
	-- Передняя стена (к полю) с дверным проёмом x -2.5..2.5, высота 8
	wall(Vector3.new(12.5, wallH, 1), Vector3.new(-8.75, wallH / 2, 62))
	wall(Vector3.new(12.5, wallH, 1), Vector3.new(8.75, wallH / 2, 62))
	wall(Vector3.new(5, 4, 1), Vector3.new(0, 10, 62))
	-- Задняя стена
	wall(Vector3.new(30, wallH, 1), Vector3.new(0, wallH / 2, 86))
	-- Боковые стены с окном (z 72..76, y 4..8)
	for _, x in { -15, 15 } do
		wall(Vector3.new(1, 4, 24), Vector3.new(x, 2, 74))
		wall(Vector3.new(1, 4, 24), Vector3.new(x, 10, 74))
		wall(Vector3.new(1, 4, 10), Vector3.new(x, 6, 67))
		wall(Vector3.new(1, 4, 10), Vector3.new(x, 6, 81))
		local glass = part(house, "Window", Vector3.new(0.3, 4, 4), CFrame.new(x, 6, 74), Color3.fromRGB(180, 200, 210), Enum.Material.Glass)
		glass.Transparency = 0.6
	end
	part(house, "Floor", Vector3.new(30, 0.4, 24), CFrame.new(0, 0.2, 74), DARK_WOOD, Enum.Material.WoodPlanks)
	part(house, "Roof", Vector3.new(32, 1, 26), CFrame.new(0, 12.5, 74), Color3.fromRGB(80, 60, 50), Enum.Material.Slate)

	-- Мебель
	part(house, "Bed", Vector3.new(5, 2, 8), CFrame.new(-10, 1.2, 70), Color3.fromRGB(150, 140, 120), Enum.Material.Fabric)
	part(house, "Table", Vector3.new(5, 3, 3), CFrame.new(8, 1.7, 68), WOOD, Enum.Material.Wood)

	-- Шкафы, где можно спрятаться
	local closets = Instance.new("Folder")
	closets.Name = "Closets"
	closets.Parent = house
	for i, x in { -11.5, 11.5 } do
		part(closets, "Closet" .. i, Vector3.new(4, 7, 3), CFrame.new(x, 3.9, 83.5), DARK_WOOD, Enum.Material.Wood)
	end

	-- Лампочка под потолком
	local bulb = part(house, "HouseLight", Vector3.new(0.8, 0.8, 0.8), CFrame.new(0, 11.3, 74), Color3.fromRGB(255, 220, 160), Enum.Material.Neon)
	local bulbLight = Instance.new("PointLight")
	bulbLight.Range = 28
	bulbLight.Brightness = 1.5
	bulbLight.Color = Color3.fromRGB(255, 210, 150)
	bulbLight.Parent = bulb

	-- Дверь (начинает открытой). Петля слева, x = -2.5
	marker(house, "DoorHinge", Vector3.new(0.5, 0.5, 0.5), Vector3.new(-2.5, 4, 62))
	part(house, "HouseDoor", Vector3.new(5, 8, 0.5), CFrame.new(0, 4.2, 62), Color3.fromRGB(90, 60, 40), Enum.Material.WoodPlanks)
	marker(house, "DoorOutside", Vector3.new(1, 1, 1), Vector3.new(0, 0, 58.5))
	marker(house, "HouseInterior", Vector3.new(29, 11, 23), Vector3.new(0, 6, 74))

	-- Точки, вокруг которых бродит Славик, когда никого не видит
	local patrol = Instance.new("Folder")
	patrol.Name = "PatrolPoints"
	patrol.Parent = map
	for i, pos in {
		Vector3.new(-20, 0, 74),
		Vector3.new(20, 0, 74),
		Vector3.new(0, 0, 92),
		Vector3.new(-8, 0, 57),
		Vector3.new(8, 0, 57),
	} do
		marker(patrol, "Patrol" .. i, Vector3.new(1, 1, 1), pos)
	end

	-- Фонари (один на всю улицу + у дома)
	lamp(map, Vector3.new(32, 0, -20), 45)
	lamp(map, Vector3.new(-20, 0, 58), 30)

	-- Старт и спавны
	marker(map, "BallSpawn", Vector3.new(1, 1, 1), Vector3.new(0, 2, 0))
	marker(map, "SpawnHouse", Vector3.new(1, 1, 1), Vector3.new(0, 3, 35))
	marker(map, "SpawnFence", Vector3.new(1, 1, 1), Vector3.new(0, 3, -35))

	local spawn = Instance.new("SpawnLocation")
	spawn.Name = "Spawn"
	spawn.Size = Vector3.new(8, 1, 8)
	spawn.CFrame = CFrame.new(24, 0.5, 40)
	spawn.Anchored = true
	spawn.Transparency = 0.5
	spawn.Duration = 0
	spawn.Neutral = true
	spawn.Parent = map

	-- Комната для пойманных (высоко над картой, со стеклянным полом)
	local spec = part(map, "Spectator", Vector3.new(30, 1, 30), CFrame.new(0, 150, 0), Color3.fromRGB(200, 220, 255), Enum.Material.Glass)
	spec.Transparency = 0.7
	for _, info in {
		{ Vector3.new(30, 8, 1), Vector3.new(0, 154, 15) },
		{ Vector3.new(30, 8, 1), Vector3.new(0, 154, -15) },
		{ Vector3.new(1, 8, 30), Vector3.new(15, 154, 0) },
		{ Vector3.new(1, 8, 30), Vector3.new(-15, 154, 0) },
	} do
		local w = part(map, "SpectatorWall", info[1], CFrame.new(info[2]), Color3.new(1, 1, 1), Enum.Material.Glass)
		w.Transparency = 0.85
	end

	map.Parent = Workspace
	return map
end

local function find(folder: Instance, name: string): BasePart
	local obj = folder:FindFirstChild(name, true)
	assert(obj and obj:IsA("BasePart"), "[MapBuilder] В папке Map не найдена деталь: " .. name)
	return obj :: BasePart
end

local function children(folder: Instance, name: string): { BasePart }
	local result: { BasePart } = {}
	local holder = folder:FindFirstChild(name, true)
	if holder then
		for _, c in holder:GetChildren() do
			if c:IsA("BasePart") then
				table.insert(result, c)
			end
		end
	end
	return result
end

function MapBuilder.load(): Map
	local folder = Workspace:FindFirstChild("Map")
	if not folder then
		folder = build()
		print("[MapBuilder] Построена карта-заглушка")
	else
		print("[MapBuilder] Используется готовая карта Workspace.Map")
	end
	assert(folder)

	local light = folder:FindFirstChild("HouseLight", true)

	return {
		Folder = folder,
		BallSpawn = find(folder, "BallSpawn"),
		GoalHouse = find(folder, "GoalHouse"),
		GoalFence = find(folder, "GoalFence"),
		FenceZone = find(folder, "FenceZone"),
		SlavikSpot = find(folder, "SlavikSpot"),
		SpawnHouse = find(folder, "SpawnHouse"),
		SpawnFence = find(folder, "SpawnFence"),
		HouseDoor = find(folder, "HouseDoor"),
		DoorHinge = find(folder, "DoorHinge"),
		DoorOutside = find(folder, "DoorOutside"),
		HouseInterior = find(folder, "HouseInterior"),
		HouseLight = if light and light:IsA("BasePart") then light else nil,
		Closets = children(folder, "Closets"),
		PatrolPoints = children(folder, "PatrolPoints"),
		Spectator = find(folder, "Spectator"),
		FieldCenter = Vector3.new(0, 0, 0),
		FieldHalfSize = Vector3.new(35, 0, 98),
	}
end

-- Точка внутри детали? (для ворот, зоны за сеткой, дома)
function MapBuilder.inside(p: BasePart, pos: Vector3): boolean
	local rel = p.CFrame:PointToObjectSpace(pos)
	local h = p.Size / 2
	return math.abs(rel.X) <= h.X and math.abs(rel.Y) <= h.Y and math.abs(rel.Z) <= h.Z
end

return MapBuilder
