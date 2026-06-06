interface PlaceholderProps {
  title: string;
}

export default function Placeholder({ title }: PlaceholderProps) {
  return (
    <div className="text-base-content/40 text-center py-12">
      <p className="text-lg">{title}</p>
      <p className="text-sm mt-2">待迁移</p>
    </div>
  );
}
