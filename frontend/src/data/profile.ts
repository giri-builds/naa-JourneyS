export const profile = {
  name: "g!r!'$",
  place: 'Miyapur, Hyderabad, India',
  timezone: 'Asia/Kolkata',
};

export const interests: string[] = [
  '🤖 AI / LLMs',
  '🧑‍💻 Coding',
  '🛠️ Building',
  '📚 Reading',
  '🏃 Running',
  '🧘 Meditation',
  '🎵 Music',
  '☕ Coffee',
  '🏔️ Trekking',
  '🍳 Cooking',
  '🎬 Movies',
  '✈️ Travel',
];

export interface ScheduleSlot {
  from: string;
  to: string;
  label: string;
}

export const schedule: ScheduleSlot[] = [
  { from: '22:00', to: '05:00', label: '😴 Sleeping' },
  { from: '05:30', to: '07:00', label: '💪 Workout' },
  { from: '07:00', to: '08:00', label: '🌅 Morning routine' },
  { from: '08:00', to: '09:00', label: '👨‍👩‍👦 Commuting' },
  { from: '09:00', to: '13:00', label: '💻 Deep work' },
  { from: '13:00', to: '14:00', label: '🍽️ Lunch' },
  { from: '14:00', to: '17:00', label: '🤝 Coding & meetings' },
  { from: '17:00', to: '18:00', label: '👨‍👩‍👦 Commuting' },
  { from: '18:00', to: '19:30', label: '🏃 Play time with Kids' },
  { from: '19:30', to: '21:00', label: '🍴 Dinner & Family' },
  { from: '21:00', to: '22:00', label: '📚 Reading / reflection' },
];
