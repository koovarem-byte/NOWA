--!strict
-- Управление:
--   Удар: держи ЛКМ или F и отпусти (чем дольше держишь — тем сильнее). На телефоне — кнопка «УДАР».
--   Красться: C или Ctrl (переключатель). На телефоне — кнопка «КРАСТЬСЯ».

local Players = game:GetService("Players")
local UserInputService = game:GetService("UserInputService")
local RunService = game:GetService("RunService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Config = require(Shared:WaitForChild("Config")) :: any
local Remotes = require(Shared:WaitForChild("Remotes")) :: any

local player = Players.LocalPlayer
local kickRemote: RemoteEvent = Remotes.get("Kick")
local state: Instance = Remotes.state()

local chargeStart: number? = nil
local sneaking = false

-- ===== Кнопки на экране =====
local gui = Instance.new("ScreenGui")
gui.Name = "Controls"
gui.ResetOnSpawn = false
gui.Parent = player:WaitForChild("PlayerGui")

local function makeButton(text: string, pos: UDim2, color: Color3): TextButton
	local b = Instance.new("TextButton")
	b.Size = UDim2.fromOffset(110, 110)
	b.AnchorPoint = Vector2.new(1, 1)
	b.Position = pos
	b.BackgroundColor3 = color
	b.BackgroundTransparency = 0.25
	b.Text = text
	b.TextScaled = true
	b.Font = Enum.Font.GothamBlack
	b.TextColor3 = Color3.new(1, 1, 1)
	b.AutoButtonColor = true
	local corner = Instance.new("UICorner")
	corner.CornerRadius = UDim.new(1, 0)
	corner.Parent = b
	local pad = Instance.new("UIPadding")
	pad.PaddingLeft = UDim.new(0, 14)
	pad.PaddingRight = UDim.new(0, 14)
	pad.Parent = b
	b.Parent = gui
	return b
end

local kickButton = makeButton("УДАР", UDim2.new(1, -30, 1, -150), Color3.fromRGB(200, 70, 50))
local sneakButton = makeButton("КРАСТЬСЯ", UDim2.new(1, -150, 1, -40), Color3.fromRGB(60, 60, 80))

-- Полоска силы удара
local chargeBack = Instance.new("Frame")
chargeBack.Size = UDim2.fromOffset(220, 14)
chargeBack.AnchorPoint = Vector2.new(0.5, 1)
chargeBack.Position = UDim2.new(0.5, 0, 1, -110)
chargeBack.BackgroundColor3 = Color3.fromRGB(20, 20, 20)
chargeBack.BackgroundTransparency = 0.3
chargeBack.Visible = false
chargeBack.Parent = gui
local chargeFill = Instance.new("Frame")
chargeFill.Size = UDim2.fromScale(0, 1)
chargeFill.BackgroundColor3 = Color3.fromRGB(255, 200, 60)
chargeFill.BorderSizePixel = 0
chargeFill.Parent = chargeBack

local hint = Instance.new("TextLabel")
hint.Size = UDim2.fromOffset(420, 22)
hint.AnchorPoint = Vector2.new(0.5, 1)
hint.Position = UDim2.new(0.5, 0, 1, -8)
hint.BackgroundTransparency = 1
hint.TextColor3 = Color3.fromRGB(220, 220, 220)
hint.TextStrokeTransparency = 0.5
hint.Font = Enum.Font.Gotham
hint.TextSize = 14
hint.Text = "ЛКМ / F — удар (держи для силы)   ·   C — красться"
hint.Parent = gui

local isTouch = UserInputService.TouchEnabled and not UserInputService.KeyboardEnabled
hint.Visible = not isTouch

-- ===== Логика =====

local function getCharge(): number
	local start = chargeStart
	if not start then
		return 0
	end
	return math.clamp((os.clock() - start) / Config.KickChargeTime, 0, 1)
end

local function beginCharge()
	if state:GetAttribute("Phase") ~= "Football" then
		return
	end
	chargeStart = os.clock()
	chargeBack.Visible = true
end

local function releaseCharge()
	if not chargeStart then
		return
	end
	local power = getCharge()
	chargeStart = nil
	chargeBack.Visible = false
	kickRemote:FireServer(power)
end

local function applySpeed()
	local char = player.Character
	local hum = char and char:FindFirstChildOfClass("Humanoid")
	if hum then
		hum.WalkSpeed = if sneaking then Config.SneakSpeed else Config.NormalSpeed
	end
	sneakButton.BackgroundColor3 = if sneaking then Color3.fromRGB(70, 140, 90) else Color3.fromRGB(60, 60, 80)
end

local function toggleSneak()
	sneaking = not sneaking
	applySpeed()
end

UserInputService.InputBegan:Connect(function(input, processed)
	if processed then
		return
	end
	if input.KeyCode == Enum.KeyCode.F or input.UserInputType == Enum.UserInputType.MouseButton1 then
		beginCharge()
	elseif input.KeyCode == Enum.KeyCode.C or input.KeyCode == Enum.KeyCode.LeftControl then
		toggleSneak()
	end
end)

UserInputService.InputEnded:Connect(function(input)
	if input.KeyCode == Enum.KeyCode.F or input.UserInputType == Enum.UserInputType.MouseButton1 then
		releaseCharge()
	end
end)

kickButton.InputBegan:Connect(function(input)
	if input.UserInputType == Enum.UserInputType.Touch or input.UserInputType == Enum.UserInputType.MouseButton1 then
		beginCharge()
	end
end)
kickButton.InputEnded:Connect(function(input)
	if input.UserInputType == Enum.UserInputType.Touch or input.UserInputType == Enum.UserInputType.MouseButton1 then
		releaseCharge()
	end
end)
sneakButton.Activated:Connect(toggleSneak)

RunService.RenderStepped:Connect(function()
	if chargeStart then
		chargeFill.Size = UDim2.fromScale(getCharge(), 1)
	end
end)

local function onPhase()
	local phase = state:GetAttribute("Phase")
	kickButton.Visible = phase == "Football"
	if phase ~= "Football" then
		chargeStart = nil
		chargeBack.Visible = false
	end
end
state:GetAttributeChangedSignal("Phase"):Connect(onPhase)
onPhase()

player.CharacterAdded:Connect(function(char)
	char:WaitForChild("Humanoid")
	applySpeed()
end)
if player.Character then
	applySpeed()
end
