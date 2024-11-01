function GiftGrid({ gifts }) {
  if (!gifts.length) {
    return null
  }

  return (
    <div className="mt-8 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {gifts.map((gift) => (
        <div
          key={gift.id}
          className="bg-white rounded-lg shadow-md overflow-hidden hover:shadow-lg transition-shadow"
        >
          {gift.image_path && (
            <img
              src={`http://localhost:5000${gift.image_path}`}
              alt={gift.name}
              className="w-full h-48 object-cover"
            />
          )}
          <div className="p-4">
            <h3 className="text-lg font-semibold text-gray-800 mb-2">
              {gift.name}
            </h3>
            <p className="text-gray-600 mb-4">
              {gift.description?.slice(0, 100)}
              {gift.description?.length > 100 ? '...' : ''}
            </p>
            <div className="flex justify-between items-center">
              <span className="text-lg font-bold text-blue-600">
                £{gift.price.toFixed(2)}
              </span>
              <a
                href={gift.affiliate_link}
                target="_blank"
                rel="noopener noreferrer"
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
              >
                View Gift
              </a>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

export default GiftGrid 