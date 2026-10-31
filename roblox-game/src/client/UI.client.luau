--!strict
-- Интерфейс: счёт, таймер, «сон Славика», прочность двери, сообщения по центру экрана.

local Players = game:GetService("Players")
local TweenService = game:GetService("TweenService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Config = require(Shared:WaitForChild("Config")) :: any
local Remotes = require(Shared:WaitForChild("Remotes")) :: any

local player = Players.LocalPlayer
local state: Instance = Remotes.state()

local gui = Instance.new("ScreenGui")
gui.Name = "HUD"
gui.ResetOnSpawn = false
gui.IgnoreGuiInset = false
gui.Parent = player:WaitForChild("PlayerGui")

local function label(parent: Instance, size: UDim2, pos: UDim2, textSize: number): TextLabel
	local l = Instance.new("TextLabel")
	l.Size = size
	l.Position = pos
	l.AnchorPoint = Vector2.new(0.5, 0)
	l.BackgroundTransparency = 1
	l.TextColor3 = Color3.new(1, 1, 1)
	l.TextStrokeTransparency = 0.3
	l.Font = Enum.Font.GothamBold
	l.TextSize = textSize
	l.Text = ""
	l.Parent = parent
	return l
end

local scoreLabel = label(gui, UDim2.fromOffset(400, 34), UDim2.new(0.5, 0, 0, 6), 28)
local timerLabel = label(gui, UDim2.fromOffset(300, 24), UDim2.new(0.5, 0, 0, 40), 20)
local teamLabel = label(gui, UDim2.fromOffset(600, 22), UDim2.new(0.5, 0, 0, 66), 16)
teamLabel.Font = Enum.Font.Gotham

-- Полоска (для сна Славика и для двери)
local function bar(title: string, y: number, color: Color3): (Frame, Frame)
	local back = Instance.new("Frame")
	back.Size = UDim2.fromOffset(260, 18)
	back.AnchorPoint = Vector2.new(0.5, 0)
	back.Position = UDim2.new(0.5, 0, 0, y)
	back.BackgroundColor3 = Color3.fromRGB(15, 15, 20)
	back.BackgroundTransparency = 0.3
	back.Parent = gui
	local fill = Instance.new("Frame")
	fill.Size = UDim2.fromScale(0, 1)
	fill.BackgroundColor3 = color
	fill.BorderSizePixel = 0
	fill.Parent = back
	local t = Instance.new("TextLabel")
	t.Size = UDim2.fromScale(1, 1)
	t.BackgroundTransparency = 1
	t.Text = title
	t.TextColor3 = Color3.new(1, 1, 1)
	t.TextStrokeTransparency = 0.4
	t.Font = Enum.Font.GothamBold
	t.TextSize = 13
	t.ZIndex = 2
	t.Parent = back
	return back, fill
end

local angerBack, angerFill = bar("Славик спит", 92, Color3.fromRGB(200, 50, 40))
local doorBack, doorFill = bar("Дверь", 92, Color3.fromRGB(150, 110, 70))

-- Сообщение по центру
local message = label(gui, UDim2.new(0.8, 0, 0, 120), UDim2.new(0.5, 0, 0.28, 0), 30)
message.Font = Enum.Font.GothamBlack
message.TextWrapped = true
message.TextScaled = false
message.TextYAlignment = Enum.TextYAlignment.Top

local messageToken = 0
Remotes.get("Message").OnClientEvent:Connect(function(text: unknown, duration: unknown)
	if typeof(text) ~= "string" then
		return
	end
	local d = if typeof(duration) == "number" then duration else 3
	messageToken += 1
	local my = messageToken
	message.Text = text
	message.TextTransparency = 0
	message.TextStrokeTransparency = 0.3
	task.delay(d, function()
		if my == messageToken then
			TweenService:Create(message, TweenInfo.new(0.6), { TextTransparency = 1, TextStrokeTransparency = 1 }):Play()
		end
	end)
end)

local function formatTime(sec: number): string
	return string.format("%d:%02d", sec // 60, sec % 60)
end

local function refresh()
	local phase = state:GetAttribute("Phase")
	local timeLeft = (state:GetAttribute("TimeLeft") :: number?) or 0
	local sh = (state:GetAttribute("ScoreHouse") :: number?) or 0
	local sf = (state:GetAttribute("ScoreFence") :: number?) or 0
	local anger = (state:GetAttribute("Anger") :: number?) or 0
	local doorHP = (state:GetAttribute("DoorHP") :: number?) or 0
	local doorClosed = state:GetAttribute("DoorClosed") == true

	scoreLabel.Visible = phase == "Football" or phase == "End"
	scoreLabel.Text = string.format("ДОМ  %d : %d  СЕТКА", sh, sf)

	angerBack.Visible = phase == "Football"
	angerFill.Size = UDim2.fromScale(math.clamp(anger / 100, 0, 1), 1)
	local angerText = angerBack:FindFirstChildOfClass("TextLabel")
	if angerText then
		angerText.Text = if anger < 50 then "Славик спит" elseif anger < 80 then "Славик ворочается..." else "СЛАВИК ВОТ-ВОТ ПРОСНЁТСЯ"
	end

	doorBack.Visible = phase == "Horror"
	doorFill.Size = UDim2.fromScale(math.clamp(doorHP / Config.DoorMaxHP, 0, 1), 1)
	local doorText = doorBack:FindFirstChildOfClass("TextLabel")
	if doorText then
		doorText.Text = if doorHP <= 0 then "Дверь выбита!" elseif doorClosed then "Дверь закрыта" else "Дверь ОТКРЫТА (E)"
	end

	if phase == "Lobby" then
		timerLabel.Text = if timeLeft > 0 then "Старт через " .. timeLeft else "Ждём игроков..."
	elseif phase == "Football" then
		timerLabel.Text = "До темноты " .. formatTime(timeLeft)
	elseif phase == "Horror" then
		timerLabel.Text = "До рассвета " .. formatTime(timeLeft)
	else
		timerLabel.Text = ""
	end

	local team = player:GetAttribute("Team")
	if phase == "Football" and team == "House" then
		teamLabel.Text = "Ты за ДОМ — забивай в ворота у сетки (не перебей!)"
	elseif phase == "Football" and team == "Fence" then
		teamLabel.Text = "Ты за СЕТКУ — забивай в ворота у дома"
	elseif phase == "Horror" then
		teamLabel.Text = if player:GetAttribute("Caught") == true
			then "Тебя поймали. Смотри за остальными."
			elseif player:GetAttribute("Hidden") == true then "Ты в шкафу. Не дыши..."
			else "Закрой дверь (E), подпирай её (держи R), прячься в шкаф (E)"
	else
		teamLabel.Text = ""
	end
end

state.AttributeChanged:Connect(refresh)
player.AttributeChanged:Connect(refresh)
refresh()
