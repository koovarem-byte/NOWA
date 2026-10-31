--!strict
-- Атмосфера и скримеры: тряска камеры, красная вспышка, звуки.

local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local SoundService = game:GetService("SoundService")
local TweenService = game:GetService("TweenService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Config = require(Shared:WaitForChild("Config")) :: any
local Remotes = require(Shared:WaitForChild("Remotes")) :: any

local player = Players.LocalPlayer
local state: Instance = Remotes.state()

local gui = Instance.new("ScreenGui")
gui.Name = "Scare"
gui.ResetOnSpawn = false
gui.IgnoreGuiInset = true
gui.DisplayOrder = 10
gui.Parent = player:WaitForChild("PlayerGui")

local flash = Instance.new("Frame")
flash.Size = UDim2.fromScale(1, 1)
flash.BackgroundColor3 = Color3.fromRGB(120, 0, 0)
flash.BackgroundTransparency = 1
flash.BorderSizePixel = 0
flash.Parent = gui

local caughtText = Instance.new("TextLabel")
caughtText.Size = UDim2.fromScale(1, 0.3)
caughtText.Position = UDim2.fromScale(0, 0.35)
caughtText.BackgroundTransparency = 1
caughtText.Text = "СЛАВИК ПОЙМАЛ ТЕБЯ"
caughtText.TextColor3 = Color3.fromRGB(255, 60, 50)
caughtText.TextScaled = true
caughtText.Font = Enum.Font.Creepster
caughtText.TextTransparency = 1
caughtText.Parent = gui

local function play(id: string, volume: number)
	if id == "" then
		return
	end
	local s = Instance.new("Sound")
	s.SoundId = id
	s.Volume = volume
	s.Parent = SoundService
	s:Play()
	task.delay(8, function()
		s:Destroy()
	end)
end

local shakeUntil = 0
local shakePower = 0
local function shake(duration: number, power: number)
	shakeUntil = math.max(shakeUntil, os.clock() + duration)
	shakePower = math.max(shakePower, power)
end

RunService.RenderStepped:Connect(function()
	local char = player.Character
	local hum = char and char:FindFirstChildOfClass("Humanoid")
	if not hum then
		return
	end
	if os.clock() < shakeUntil then
		local p = shakePower
		hum.CameraOffset = Vector3.new((math.random() - 0.5) * p, (math.random() - 0.5) * p, (math.random() - 0.5) * p)
	elseif hum.CameraOffset ~= Vector3.zero then
		hum.CameraOffset = Vector3.zero
		shakePower = 0
	end
end)

local function flashRed(strength: number, fadeTime: number)
	flash.BackgroundTransparency = 1 - strength
	TweenService:Create(flash, TweenInfo.new(fadeTime), { BackgroundTransparency = 1 }):Play()
end

Remotes.get("Scare").OnClientEvent:Connect(function(kind: unknown)
	if kind == "wake" then
		play(Config.Sounds.Wake, 2)
		flashRed(0.6, 1.5)
		shake(1.5, 0.8)
	elseif kind == "doorhit" then
		play(Config.Sounds.DoorHit, 1.5)
		shake(0.3, 0.5)
	elseif kind == "knock" then
		play(Config.Sounds.Knock, 1.5)
		shake(0.2, 0.2)
	elseif kind == "caught" then
		play(Config.Sounds.Caught, 2.5)
		flash.BackgroundColor3 = Color3.new(0, 0, 0)
		flash.BackgroundTransparency = 0
		caughtText.TextTransparency = 0
		shake(1.2, 1.2)
		task.delay(1.8, function()
			TweenService:Create(flash, TweenInfo.new(1), { BackgroundTransparency = 1 }):Play()
			TweenService:Create(caughtText, TweenInfo.new(1), { TextTransparency = 1 }):Play()
			task.delay(1, function()
				flash.BackgroundColor3 = Color3.fromRGB(120, 0, 0)
			end)
		end)
	end
end)

-- Фоновый ночной звук во время хоррора
local ambient: Sound? = nil
local function onPhase()
	local phase = state:GetAttribute("Phase")
	if phase == "Horror" and Config.Sounds.Ambient ~= "" then
		if not ambient then
			local s = Instance.new("Sound")
			s.SoundId = Config.Sounds.Ambient
			s.Looped = true
			s.Volume = 0.6
			s.Parent = SoundService
			s:Play()
			ambient = s
		end
	elseif ambient then
		ambient:Destroy()
		ambient = nil
	end
end
state:GetAttributeChangedSignal("Phase"):Connect(onPhase)
onPhase()
